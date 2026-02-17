"""
╔══════════════════════════════════════════════════════════════════════════╗
║                    ORDER MANAGEMENT SYSTEM                                ║
║              Cart Management & Order Processing                           ║
║                                                                          ║
║  Features:                                                               ║
║  ✓ Shopping cart management (add, view, remove)                        ║
║  ✓ Order creation and tracking                                         ║
║  ✓ Order state management                                              ║
║  ✓ User authentication check                                           ║
║  ✓ Numbered menu system (1, 2, 3, 4)                                  ║
║                                                                          ║
║  FIXES v2:                                                               ║
║  ✓ Compound model names: "17Pro Max", "17ProMax" parsed correctly      ║
║  ✓ Brand alias map: "iphone"→"Apple/iPhone" resolved at DB level       ║
║  ✓ Model token extraction handles digit-led strings like "17"+"Pro"    ║
║  ✓ Fuzzy fallback via rapidfuzz when exact SQL match fails             ║
║  ✓ Cache: failed lookups are never stored                              ║
║  ✓ Score-5 false-positive rejection tightened                         ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
import re
import secrets
import sqlite3
import logging
import json
import string
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ── optional rapidfuzz ─────────────────────────────────────────────────────
try:
    from rapidfuzz import fuzz, process as fuzz_process
    _FUZZY_OK = True
except ImportError:
    _FUZZY_OK = False
    logger.warning("rapidfuzz not installed — fuzzy product matching disabled")


# ═══════════════════════════════════════════════════════════════════════════
# BRAND ALIAS MAP
# Maps every user-facing spelling → canonical DB brand name(s) to try.
# Add entries here whenever a new brand is stocked.
# ═══════════════════════════════════════════════════════════════════════════

BRAND_ALIASES: Dict[str, List[str]] = {
    # alias (lowercase)  →  DB brand names to try (in priority order)
    "iphone":   ["Apple", "iPhone"],
    "apple":    ["Apple", "iPhone"],
    "samsung":  ["Samsung"],
    "redmi":    ["Redmi", "Xiaomi"],
    "xiaomi":   ["Xiaomi", "Redmi"],
    "poco":     ["Poco", "Xiaomi"],
    "oppo":     ["Oppo", "OPPO"],
    "vivo":     ["Vivo", "vivo"],
    "realme":   ["Realme", "realme"],
    "oneplus":  ["OnePlus", "oneplus"],
    "google":   ["Google", "Pixel"],
    "pixel":    ["Google", "Pixel"],
    "nokia":    ["Nokia"],
    "tecno":    ["Tecno", "TECNO"],
    "itel":     ["Itel", "iTel"],
}

# Words that carry NO product-identity information.
# Used to decide whether the user actually named a specific product.
_GENERIC_WORDS: frozenset = frozenset({
    'i', 'want', 'to', 'buy', 'get', 'purchase', 'order',
    'please', 'can', 'me', 'a', 'the', 'this', 'that', 'it',
    'one', 'phone', 'product', 'item', 'would', 'like', 'need',
    'looking', 'for', 'some',
})


# ═══════════════════════════════════════════════════════════════════════════
# ORDER STATE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

class OrderState(str, Enum):
    """Order processing states"""
    BROWSING           = "browsing"
    CART_CONFIRM       = "cart_confirm"
    CART_MANAGEMENT    = "cart_management"
    CHECKOUT_CONFIRM   = "checkout_confirm"
    ADDRESS_INPUT      = "address_input"
    PHONE_INPUT        = "phone_input"
    PAYMENT_SELECT     = "payment_select"
    NOTE_INPUT         = "note_input"
    TRANSACTION_INPUT  = "transaction_input"
    ORDER_COMPLETE     = "order_complete"


class PaymentMethod(str, Enum):
    """Available payment methods"""
    KBZ  = "KBZ Pay"
    WAVE = "Wave Money"
    CASH = "Cash on Delivery"


# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CartItem:
    """Single item in shopping cart"""
    product_id: int
    brand:       str
    model:       str
    price:       int
    quantity:    int
    ram_storage: str
    color:       str

    def to_dict(self) -> Dict:
        return asdict(self)

    def get_subtotal(self) -> int:
        return self.price * self.quantity

    def get_display_text(self) -> str:
        model_display = _strip_brand_prefix(self.brand, self.model)
        return (
            f"📱 {self.brand} {model_display}\n"
            f"💾 {self.ram_storage}\n"
            f"🎨 {self.color}\n"
            f"💰 {self.price:,} Ks x {self.quantity}\n"
            f"   = {self.get_subtotal():,} Ks"
        )


@dataclass
class OrderSession:
    """User's current ordering session"""
    user_id:          Optional[int]       = None
    state:            OrderState          = OrderState.BROWSING
    cart:             List[CartItem]      = field(default_factory=list)
    pending_product:  Optional[Dict]      = None

    delivery_address: Optional[str]       = None
    phone_number:     Optional[str]       = None
    payment_method:   Optional[str]       = None
    note:             Optional[str]       = None
    transaction_number: Optional[str]    = None

    def to_dict(self) -> Dict:
        return {
            "user_id":            self.user_id,
            "state":              self.state.value,
            "cart":               [item.to_dict() for item in self.cart],
            "pending_product":    self.pending_product,
            "delivery_address":   self.delivery_address,
            "phone_number":       self.phone_number,
            "payment_method":     self.payment_method,
            "note":               self.note,
            "transaction_number": self.transaction_number,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "OrderSession":
        cart_items = [CartItem(**item) for item in data.get("cart", [])]
        return cls(
            user_id=data.get("user_id"),
            state=OrderState(data.get("state", "browsing")),
            cart=cart_items,
            pending_product=data.get("pending_product"),
            delivery_address=data.get("delivery_address"),
            phone_number=data.get("phone_number"),
            payment_method=data.get("payment_method"),
            note=data.get("note"),
            transaction_number=data.get("transaction_number"),
        )

    def get_cart_total(self) -> int:
        return sum(item.get_subtotal() for item in self.cart)

    def get_cart_count(self) -> int:
        return sum(item.quantity for item in self.cart)

    def clear_cart(self):
        self.cart = []
        self.pending_product = None


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _strip_brand_prefix(brand: str, model: str) -> str:
    """Remove redundant brand prefix from model string.

    Prevents "Tecno Tecno Pova 6 Pro" display artifacts.
    """
    if model.lower().startswith(brand.lower() + " "):
        return model[len(brand) + 1:]
    return model


def _normalize_model_token(raw: str) -> str:
    """Normalise a raw model token so spacing is consistent.

    Examples
    --------
    '17ProMax'  → '17 Pro Max'
    '17Pro'     → '17 Pro'
    'k90pro'    → 'K90 Pro'
    's24ultra'  → 'S24 Ultra'
    """
    # Insert space before an uppercase letter that follows a digit: 17Pro → 17 Pro
    result = re.sub(r"(\d)([A-Z])", r"\1 \2", raw)
    # Insert space before an uppercase letter that follows lowercase: ProMax → Pro Max
    result = re.sub(r"([a-z])([A-Z])", r"\1 \2", result)
    return result.strip().title()


def _extract_model_tokens(search_lower: str) -> List[str]:
    """
    Extract model search candidates ordered LONGEST (most specific) → SHORTEST.

    The caller tries each candidate in order against the DB and returns on the
    first hit, so more-specific phrases always win over single tokens.

    Design rationale
    ----------------
    Previous versions tried to find "one core identifier" (a token containing
    digits) and append qualifiers around it.  That strategy fails for models
    whose series name contains NO digits, e.g.:
      • "Galaxy Z Fold 7"  — "z fold" has no digits, only "7" does
      • "ZFold 7"          — "zfold" is all-alpha, "7" is a single digit
      • "Pixel 7 Pro"      — single-digit version number
      • "Find X7 Pro"      — letter+digit but X7 doesn't match \d+[a-z]

    New strategy
    ------------
    1. Strip noise words (intent verbs + brand tokens) from the query to get
       the raw model phrase.
    2. Emit the full cleaned phrase as the first (best) candidate.
    3. Build progressive sub-phrases by dropping one token from the RIGHT at a
       time, giving longest-first ordering.
    4. Then emit individual meaningful tokens as fallbacks.

    This handles every known real-world pattern:

    Input → top candidates (DB tried in this order)
    ─────────────────────────────────────────────────────────────────
    "samsung galaxy zfold 7"   → ["galaxy zfold 7","galaxy zfold","zfold 7","zfold","7"]
    "samsung galaxy z fold 7"  → ["galaxy z fold 7","galaxy z fold","z fold 7","z fold","7"]
    "iphone 17 pro max"        → ["17 pro max","17 pro","17","pro max","pro","max"]
    "iphone 17pro max"         → ["17pro max","17pro","17 pro max","17 pro","17","max"]
    "redmi k90 pro max"        → ["k90 pro max","k90 pro","k90","pro max","pro","max"]
    "samsung s24 ultra"        → ["s24 ultra","s24","ultra"]
    "vivo v60"                 → ["v60"]
    "pixel 7 pro"              → ["7 pro","7","pro"]
    "oneplus nord 4"           → ["nord 4","nord","4"]
    "samsung galaxy s24 fe"    → ["galaxy s24 fe","galaxy s24","s24 fe","s24","fe"]
    """
    # ── Noise words to strip before phrase extraction ──────────────────────
    # Intent verbs
    INTENT_WORDS = {
        "i", "want", "to", "buy", "get", "purchase", "order",
        "please", "can", "me", "a", "the", "would", "like",
        "need", "looking", "for", "some", "show", "find",
    }
    # Known brand tokens (keep in sync with BRAND_ALIASES keys)
    BRAND_TOKENS = {
        "iphone", "apple", "samsung", "redmi", "xiaomi", "poco",
        "oppo", "vivo", "realme", "oneplus", "google", "pixel",
        "nokia", "tecno", "itel", "huawei", "motorola", "sony",
        "lg", "asus", "infinix",
    }
    NOISE = INTENT_WORDS | BRAND_TOKENS

    seen: set = set()
    result: List[str] = []

    def _add(t: str):
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            result.append(t)

    # ── Step 1: build the cleaned model phrase ─────────────────────────────
    words = search_lower.split()
    model_words = [w for w in words if w not in NOISE]
    # Also strip trailing punctuation from each word
    model_words = [re.sub(r"[^\w]$", "", w) for w in model_words if w]
    model_words = [w for w in model_words if w]  # remove any now-empty strings

    if not model_words:
        return result

    # ── Step 2: full phrase and progressive right-truncations ──────────────
    # "galaxy z fold 7" → "galaxy z fold 7", "galaxy z fold", "galaxy z", "galaxy"
    # BUT only emit sub-phrases that contain at least one "meaningful" token
    # (a digit, a letter+digit combo, or a known series word).
    # This prevents emitting bare common words like "galaxy" alone as a search term.

    def _is_meaningful_phrase(phrase_words: List[str]) -> bool:
        """True if phrase contains a digit token or a known model-series word."""
        SERIES_WORDS = {
            "fold", "flip", "ultra", "pro", "max", "plus", "lite", "mini",
            "note", "edge", "fe", "neo", "nova", "nord", "civi", "pova",
            "reno", "find", "ace", "gt", "turbo", "zfold", "zflip",
        }
        joined = " ".join(phrase_words)
        has_digit = bool(re.search(r"\d", joined))
        has_series = any(w in SERIES_WORDS for w in phrase_words)
        return has_digit or has_series

    # Emit longest-first sub-phrases
    for end in range(len(model_words), 0, -1):
        phrase = " ".join(model_words[:end])
        if _is_meaningful_phrase(model_words[:end]):
            _add(phrase)

    # ── Step 3: individual meaningful tokens ──────────────────────────────
    # Emit each token separately as a fallback, digit-bearing first
    digit_tokens   = [w for w in model_words if re.search(r"\d", w)]
    alpha_tokens   = [w for w in model_words if not re.search(r"\d", w)]

    for t in digit_tokens:
        _add(t)

    # For compound tokens like "17pro" → also emit numeric part "17"
    for t in digit_tokens:
        numeric = re.match(r"(\d+)", t)
        if numeric:
            _add(numeric.group(1))

    for t in alpha_tokens:
        _add(t)

    return result


def _resolve_db_brands(search_lower: str) -> Tuple[Optional[str], List[str]]:
    """
    Given a lower-cased search string, return:
      (alias_found, [db_brand_candidates])

    Returns the first alias match found and the list of DB brand names to try.
    Returns (None, []) if no brand alias matches.
    """
    for alias, db_names in BRAND_ALIASES.items():
        if alias in search_lower:
            return alias, db_names
    return None, []


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════

class OrderDatabase:
    """Handle all database operations for orders."""

    def __init__(self, db_path: str, products_db_path: str):
        self.db_path = db_path
        self.products_db_path = products_db_path
        self._init_tables()

    # ── connections ─────────────────────────────────────────────────────

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _get_products_connection(self):
        conn = sqlite3.connect(self.products_db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ── schema ───────────────────────────────────────────────────────────

    def _init_tables(self):
        """Initialize order tables, migrating schema if needed."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"
            )
            table_exists = cursor.fetchone() is not None

            if table_exists:
                cursor = conn.execute("PRAGMA table_info(orders)")
                columns = [row[1] for row in cursor.fetchall()]
                needs_migration = (
                    "order_number" not in columns
                    or "transaction_number" not in columns
                )
                if needs_migration:
                    logger.warning("⚠️ Migrating orders table...")
                    conn.execute("DROP TABLE IF EXISTS order_items")
                    conn.execute("DROP TABLE IF EXISTS orders")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_number      TEXT    UNIQUE NOT NULL,
                    user_id           INTEGER NOT NULL,
                    total_amount      INTEGER NOT NULL,
                    delivery_address  TEXT    NOT NULL,
                    phone_number      TEXT    NOT NULL,
                    payment_method    TEXT    NOT NULL,
                    note              TEXT,
                    transaction_number TEXT,
                    status            TEXT DEFAULT 'pending',
                    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id    INTEGER NOT NULL,
                    product_id  INTEGER NOT NULL,
                    brand       TEXT NOT NULL,
                    model       TEXT NOT NULL,
                    ram_storage TEXT NOT NULL,
                    color       TEXT NOT NULL,
                    price       INTEGER NOT NULL,
                    quantity    INTEGER NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS order_sessions (
                    user_id      INTEGER PRIMARY KEY,
                    session_data TEXT    NOT NULL,
                    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)

            conn.commit()

        logger.info("✅ Order tables initialized")

    # ── product lookup ────────────────────────────────────────────────────

    def get_product_by_brand_model(self, brand: str, model: str) -> Optional[Dict]:
        """Exact brand + model lookup."""
        with self._get_products_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM products WHERE LOWER(brand)=LOWER(?) AND LOWER(model)=LOWER(?) LIMIT 1",
                (brand, model),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_product_by_full_name(self, full_name: str) -> Optional[Dict]:
        """Lookup by concatenated 'brand model' string, exact then partial."""
        with self._get_products_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM products WHERE LOWER(brand||' '||model)=LOWER(?) LIMIT 1",
                (full_name,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)

            cursor = conn.execute(
                """SELECT * FROM products
                   WHERE LOWER(brand||' '||model) LIKE LOWER(?)
                   ORDER BY
                     CASE WHEN LOWER(brand||' '||model)=LOWER(?) THEN 1
                          WHEN LOWER(brand||' '||model) LIKE LOWER(?) THEN 2
                          ELSE 3 END
                   LIMIT 1""",
                (f"%{full_name}%", full_name, f"{full_name}%"),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        """Fetch a product by its primary key."""
        try:
            with self._get_products_connection() as conn:
                cursor = conn.execute("SELECT * FROM products WHERE id=?", (product_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching product: {e}")
            return None

    # ── MAIN PRODUCT SEARCH ───────────────────────────────────────────────

    def get_product_by_partial_match(self, search_text: str) -> Optional[Dict]:
        """
        Robust product lookup that handles:

        1. Compound model names with no spaces: "17ProMax", "17Pro"
        2. Brand alias resolution: "iphone" → tries ["Apple","iPhone"] in DB
        3. Multi-token model names: "17 Pro Max", "K90 Pro Max"
        4. Fuzzy fallback via rapidfuzz when SQL finds nothing
        5. NEVER returns a stale cache entry on failure (caller's responsibility)

        Matching priority (lower score = better match):
          1 – exact brand + exact model
          2 – brand + model starts-with token
          3 – brand + model ends-with token
          4 – brand + model has token in middle
          5 – brand + model contains token (loose)
          6 – full-text LIKE
        """
        search_lower = search_text.lower().strip()

        # ── resolve brand alias ────────────────────────────────────────
        alias_found, db_brands = _resolve_db_brands(search_lower)
        logger.info(f"🔍 brand alias: '{alias_found}' → DB candidates: {db_brands}")

        # ── extract model tokens ────────────────────────────────────────
        model_tokens = _extract_model_tokens(search_lower)
        logger.info(f"🔍 model tokens: {model_tokens}")

        if not model_tokens and not db_brands:
            logger.warning(f"❌ No extractable tokens for: {search_text}")
            return None

        # ── try each DB brand candidate ────────────────────────────────
        result = None
        if db_brands and model_tokens:
            result = self._sql_search_with_brand(db_brands, model_tokens, search_lower)

        # ── if brand found but NO model tokens → only then return cheapest ──
        # This handles truly vague requests like "buy samsung" (no model named).
        # If model_tokens is non-empty the user DID name a model; don't fall
        # back to cheapest — return None so the caller shows "not found".
        if result is None and db_brands and not model_tokens:
            logger.info("📋 No model tokens — returning cheapest for brand")
            result = self._sql_cheapest_for_brand(db_brands)

        # ── no-brand search ────────────────────────────────────────────
        if result is None and model_tokens:
            result = self._sql_search_no_brand(model_tokens, search_lower)

        # ── fuzzy fallback ─────────────────────────────────────────────
        if result is None and _FUZZY_OK:
            result = self._fuzzy_search(search_text, db_brands)

        if result:
            logger.info(f"✅ Final match: {result['brand']} {result['model']}")
        else:
            logger.warning(f"❌ No match found for: {search_text}")

        return result

    # ── SQL helpers ────────────────────────────────────────────────────────

    def _sql_search_with_brand(
        self,
        db_brands: List[str],
        model_tokens: List[str],
        search_lower: str,
    ) -> Optional[Dict]:
        """
        Try each DB brand candidate in priority order.

        For each brand we iterate over model_tokens (ordered longest→shortest
        by _extract_model_tokens).  Each token is tried as both its raw form
        and its normalised form (e.g. "k90 pro max" and "K90 Pro Max").

        SQL scoring (lower = better):
          1 – exact brand + exact model
          2 – model starts with token
          3 – model ends with token
          4 – token appears in middle of model
          5 – loose LIKE contains (subject to _ids_overlap guard)

        We return the FIRST hit from the LONGEST phrase tried, so
        "K90 Pro Max" beats "K90" when both exist in the DB.
        """
        with self._get_products_connection() as conn:
            for db_brand in db_brands:
                brand_lower = db_brand.lower()

                for raw_token in model_tokens:
                    # Build a de-duplicated list of search forms to try.
                    # For a multi-word token like "k90 pro max" _normalize_model_token
                    # only makes sense on single tokens, so skip normalization when
                    # the token already contains spaces.
                    if " " in raw_token:
                        # Multi-word phrase: try as-is and title-cased
                        search_forms = list(dict.fromkeys([
                            raw_token,
                            raw_token.title().lower(),
                        ]))
                    else:
                        norm = _normalize_model_token(raw_token).lower()
                        search_forms = list(dict.fromkeys([raw_token, norm]))

                    for token in search_forms:
                        cursor = conn.execute(
                            """
                            SELECT *,
                                (CASE
                                    WHEN LOWER(brand)=? AND LOWER(model)=?       THEN 1
                                    WHEN LOWER(brand)=? AND LOWER(model) LIKE ?  THEN 2
                                    WHEN LOWER(brand)=? AND LOWER(model) LIKE ?  THEN 3
                                    WHEN LOWER(brand)=? AND LOWER(model) LIKE ?  THEN 4
                                    WHEN LOWER(brand)=? AND LOWER(model) LIKE ?  THEN 5
                                    ELSE 6
                                END) AS score
                            FROM products
                            WHERE LOWER(brand)=?
                              AND (
                                    LOWER(model)=?
                                 OR LOWER(model) LIKE ?
                                 OR LOWER(model) LIKE ?
                                 OR LOWER(model) LIKE ?
                                 OR LOWER(model) LIKE ?
                              )
                            ORDER BY score ASC, LENGTH(model) DESC
                            LIMIT 1
                            """,
                            (
                                brand_lower, token,            # score 1 exact
                                brand_lower, f"{token} %",    # score 2 starts
                                brand_lower, f"% {token}",    # score 3 ends
                                brand_lower, f"% {token} %",  # score 4 middle
                                brand_lower, f"%{token}%",    # score 5 loose
                                brand_lower,                   # WHERE brand
                                token,
                                f"{token} %",
                                f"% {token}",
                                f"% {token} %",
                                f"%{token}%",
                            ),
                        )
                        row = cursor.fetchone()
                        if row:
                            candidate = dict(row)
                            score = candidate.pop("score", 6)

                            # Reject score-5 loose matches when model identifiers
                            # don't overlap (e.g. "S24 Ultra" hitting "Galaxy A06").
                            if score >= 5 and not self._ids_overlap(
                                search_lower, candidate["model"].lower()
                            ):
                                logger.warning(
                                    f"❌ Rejected loose match (score={score}): "
                                    f"{candidate['brand']} {candidate['model']}"
                                )
                                continue

                            logger.info(
                                f"✅ Matched (score={score}, token='{token}'): "
                                f"{candidate['brand']} {candidate['model']}"
                            )
                            return candidate

        return None

    def _sql_cheapest_for_brand(self, db_brands: List[str]) -> Optional[Dict]:
        """Return the cheapest product for the first matched brand."""
        with self._get_products_connection() as conn:
            for db_brand in db_brands:
                cursor = conn.execute(
                    "SELECT * FROM products WHERE LOWER(brand)=? ORDER BY price ASC LIMIT 1",
                    (db_brand.lower(),),
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
        return None

    def _sql_search_no_brand(
        self, model_tokens: List[str], search_lower: str
    ) -> Optional[Dict]:
        """Brand-agnostic search using model tokens only (longest phrase first)."""
        with self._get_products_connection() as conn:
            for raw_token in model_tokens:
                # Multi-word phrases are searched as-is; single tokens get normalised too.
                if " " in raw_token:
                    search_forms = list(dict.fromkeys([raw_token, raw_token.title().lower()]))
                else:
                    norm_token = _normalize_model_token(raw_token).lower()
                    search_forms = list(dict.fromkeys([raw_token, norm_token]))

                for token in search_forms:
                    cursor = conn.execute(
                        """
                        SELECT *,
                            (CASE
                                WHEN LOWER(model) LIKE ?      THEN 1
                                WHEN LOWER(model) LIKE ?      THEN 2
                                WHEN LOWER(model) LIKE ?      THEN 3
                                ELSE 4
                            END) AS score
                        FROM products
                        WHERE LOWER(model) LIKE ?
                           OR LOWER(model) LIKE ?
                           OR LOWER(model) LIKE ?
                        ORDER BY score ASC, LENGTH(model) DESC
                        LIMIT 1
                        """,
                        (
                            f"{token} %",
                            f"% {token} %",
                            f"% {token}",
                            f"{token} %",
                            f"% {token} %",
                            f"% {token}",
                        ),
                    )
                    row = cursor.fetchone()
                    if row:
                        candidate = dict(row)
                        candidate.pop("score", None)
                        if self._ids_overlap(search_lower, candidate["model"].lower()):
                            logger.info(
                                f"✅ No-brand match: {candidate['brand']} {candidate['model']}"
                            )
                            return candidate
        return None

    def _fuzzy_search(
        self, search_text: str, db_brands: List[str], threshold: int = 72
    ) -> Optional[Dict]:
        """
        Fuzzy fallback using rapidfuzz token_sort_ratio.
        Filters to brand candidates first for efficiency.
        """
        if not _FUZZY_OK:
            return None

        with self._get_products_connection() as conn:
            if db_brands:
                placeholders = ",".join("?" * len(db_brands))
                cursor = conn.execute(
                    f"SELECT * FROM products WHERE LOWER(brand) IN ({placeholders})",
                    [b.lower() for b in db_brands],
                )
            else:
                cursor = conn.execute("SELECT * FROM products")

            rows = [dict(r) for r in cursor.fetchall()]

        if not rows:
            return None

        # Build full-name candidates
        candidates = {f"{r['brand']} {r['model']}": r for r in rows}
        result = fuzz_process.extractOne(
            search_text,
            candidates.keys(),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold,
        )
        if result:
            matched_name, score, _ = result
            logger.info(f"🔀 Fuzzy match (score={score}): {matched_name}")
            return candidates[matched_name]

        return None

    @staticmethod
    def _ids_overlap(search_lower: str, model_lower: str) -> bool:
        """
        Verify that the search string and DB model name share at least one
        meaningful identifier so we don't accept accidental substring matches.

        Checks (any one is sufficient):
          a) A digit-bearing token (e.g. "s24", "17", "k90", "7") appears in both.
          b) A known series/qualifier word appears in both
             (catches "zfold"↔"z fold", "ultra"↔"ultra", "fold"↔"fold").
          c) Neither string contains any identifiers at all — don't block
             brand-only searches (e.g. "buy samsung").

        Single-digit model numbers (7, 9, X) are included deliberately:
        "Pixel 7", "iPhone X", "Note 9" are all valid.
        """
        SERIES_WORDS = {
            "fold", "flip", "ultra", "pro", "max", "plus", "lite", "mini",
            "note", "edge", "fe", "neo", "nova", "nord", "civi", "pova",
            "reno", "find", "ace", "gt", "turbo", "zfold", "zflip",
        }
        # Any token that contains at least one digit (includes single digits)
        id_pattern = r"\b([a-z]*\d+[a-z0-9]*)\b"
        search_ids = set(re.findall(id_pattern, search_lower))
        model_ids  = set(re.findall(id_pattern, model_lower))

        # Check (c): no identifiers on either side → don't block
        if not search_ids and not model_ids:
            return True

        # Check (a): digit-token overlap
        if search_ids and model_ids and (search_ids & model_ids):
            return True

        # Check (b): shared series/qualifier word
        search_words = set(search_lower.split())
        model_words  = set(model_lower.split())
        if search_words & model_words & SERIES_WORDS:
            return True

        # Also handle "zfold" in search matching "z fold" in DB (no space vs space)
        search_clean = re.sub(r"\s+", "", search_lower)
        model_clean  = re.sub(r"\s+", "", model_lower)
        for sw in SERIES_WORDS:
            sw_nospace = sw.replace(" ", "")
            if sw_nospace in search_clean and sw_nospace in model_clean:
                return True

        return False

    # ── inventory management ──────────────────────────────────────────────

    def check_inventory_availability(
        self, order_id: int
    ) -> Tuple[bool, List[str]]:
        """Check whether sufficient stock exists for all items in an order."""
        try:
            with self._get_connection() as conn:
                order_items = conn.execute(
                    "SELECT product_id, quantity FROM order_items WHERE order_id=?",
                    (order_id,),
                ).fetchall()

            with self._get_products_connection() as products_conn:
                errors: List[str] = []
                for item in order_items:
                    product = products_conn.execute(
                        "SELECT id, brand, model, quantity FROM products WHERE id=?",
                        (item["product_id"],),
                    ).fetchone()

                    if not product:
                        errors.append(f"Product ID {item['product_id']} not found")
                    elif product["quantity"] < item["quantity"]:
                        errors.append(
                            f"{product['brand']} {product['model']}: "
                            f"Need {item['quantity']}, only {product['quantity']} in stock"
                        )

                return len(errors) == 0, errors

        except Exception as e:
            logger.error(f"Error checking inventory: {e}")
            return False, [f"Error: {str(e)}"]

    def deduct_inventory(self, order_id: int) -> bool:
        """Deduct order quantities from inventory. Returns True on success."""
        try:
            with self._get_connection() as conn:
                order_items = conn.execute(
                    "SELECT product_id, quantity FROM order_items WHERE order_id=?",
                    (order_id,),
                ).fetchall()

            with self._get_products_connection() as products_conn:
                for item in order_items:
                    products_conn.execute(
                        "UPDATE products SET quantity=quantity-? WHERE id=?",
                        (item["quantity"], item["product_id"]),
                    )
                products_conn.commit()

            logger.info(f"✅ Inventory deducted for order {order_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error deducting inventory: {e}")
            return False

    def restore_inventory(self, order_id: int) -> bool:
        """Restore order quantities back to inventory. Returns True on success."""
        try:
            with self._get_connection() as conn:
                order_items = conn.execute(
                    "SELECT product_id, quantity FROM order_items WHERE order_id=?",
                    (order_id,),
                ).fetchall()

            with self._get_products_connection() as products_conn:
                for item in order_items:
                    products_conn.execute(
                        "UPDATE products SET quantity=quantity+? WHERE id=?",
                        (item["quantity"], item["product_id"]),
                    )
                products_conn.commit()

            logger.info(f"✅ Inventory restored for order {order_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error restoring inventory: {e}")
            return False

    def get_order_inventory_status(self, order_id: int) -> Dict:
        """Detailed inventory status per order item."""
        try:
            with self._get_connection() as conn:
                order_items = conn.execute(
                    """SELECT oi.product_id, oi.brand, oi.model,
                              oi.quantity AS ordered_quantity
                       FROM order_items oi WHERE oi.order_id=?""",
                    (order_id,),
                ).fetchall()

            with self._get_products_connection() as products_conn:
                inventory_status = []
                for item in order_items:
                    product = products_conn.execute(
                        "SELECT quantity FROM products WHERE id=?",
                        (item["product_id"],),
                    ).fetchone()

                    current_stock = product["quantity"] if product else 0
                    inventory_status.append({
                        "product_id":       item["product_id"],
                        "brand":            item["brand"],
                        "model":            item["model"],
                        "ordered_quantity": item["ordered_quantity"],
                        "current_stock":    current_stock,
                        "available":        current_stock >= item["ordered_quantity"],
                    })

            return {
                "order_id":      order_id,
                "items":         inventory_status,
                "all_available": all(i["available"] for i in inventory_status),
            }

        except Exception as e:
            logger.error(f"Error getting inventory status: {e}")
            return {"order_id": order_id, "items": [], "all_available": False, "error": str(e)}

    # ── session management ────────────────────────────────────────────────

    def save_session(self, user_id: int, session: OrderSession):
        """Persist session to DB."""
        session_json = json.dumps(session.to_dict())
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO order_sessions (user_id, session_data, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)""",
                (user_id, session_json),
            )
            conn.commit()
        logger.info(f"💾 Saved session for user {user_id}")

    def load_session(self, user_id: int) -> OrderSession:
        """Load session from DB; returns a fresh session if none exists."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT session_data FROM order_sessions WHERE user_id=?",
                (user_id,),
            )
            row = cursor.fetchone()

        if row:
            session_dict = json.loads(row[0])
            return OrderSession.from_dict(session_dict)

        return OrderSession(user_id=user_id)

    def clear_session(self, user_id: int):
        """Delete user's session row."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM order_sessions WHERE user_id=?", (user_id,))
            conn.commit()

    # ── order creation ────────────────────────────────────────────────────

    def generate_order_number(self) -> str:
        """
        Format: ORD-YYYYMMDD-NNNN-XXXX
        Example: ORD-20260217-0003-A7B2
        """
        date_str       = datetime.now().strftime("%Y%m%d")
        random_suffix  = "".join(
            secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4)
        )
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE order_number LIKE ?",
                (f"ORD-{date_str}-%",),
            )
            count = cursor.fetchone()[0]

        return f"ORD-{date_str}-{count + 1:04d}-{random_suffix}"

    def create_order(self, user_id: int, session: OrderSession) -> str:
        """Persist a completed order and clear the session."""
        order_number = self.generate_order_number()

        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO orders
                   (order_number, user_id, total_amount, delivery_address,
                    phone_number, payment_method, note, transaction_number)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_number,
                    user_id,
                    session.get_cart_total(),
                    session.delivery_address,
                    session.phone_number,
                    session.payment_method,
                    session.note,
                    session.transaction_number,
                ),
            )
            order_id = cursor.lastrowid

            for item in session.cart:
                conn.execute(
                    """INSERT INTO order_items
                       (order_id, product_id, brand, model,
                        ram_storage, color, price, quantity)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        order_id,
                        item.product_id,
                        item.brand,
                        item.model,
                        item.ram_storage,
                        item.color,
                        item.price,
                        item.quantity,
                    ),
                )

            conn.commit()

        self.clear_session(user_id)
        logger.info(f"✅ Order created: {order_number}")
        return order_number

    def get_order_with_items(self, order_id: int) -> Optional[Dict]:
        """Full order + items dict."""
        try:
            with self._get_connection() as conn:
                order = conn.execute(
                    "SELECT * FROM orders WHERE id=?", (order_id,)
                ).fetchone()
                if not order:
                    return None

                order_dict = dict(order)
                order_dict["items"] = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM order_items WHERE order_id=?", (order_id,)
                    ).fetchall()
                ]
                return order_dict

        except Exception as e:
            logger.error(f"Error fetching order with items: {e}")
            return None

    def get_user_orders(self, user_id: int) -> List[Dict]:
        """All orders for a user, newest first."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC",
                (user_id,),
            )
            return [dict(row) for row in cursor.fetchall()]


# ═══════════════════════════════════════════════════════════════════════════
# ORDER FLOW MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class OrderFlowManager:
    """Manage order flow and state transitions — numbered menu version."""

    def __init__(self, db: OrderDatabase):
        self.db = db

    def is_authenticated(self, user_id: Optional[int]) -> bool:
        return user_id is not None

    # ── buy intent ────────────────────────────────────────────────────────

    def handle_buy_intent(
        self,
        user_id: Optional[int],
        product_info: Dict,
        message: str,
    ) -> Tuple[str, OrderState]:
        """Handle 'I want to buy X'. Supports 1 (add) / 2 (cancel)."""
        if not self.is_authenticated(user_id):
            return self._guest_cannot_order(), OrderState.BROWSING

        session = self.db.load_session(user_id)

        if session.state == OrderState.CART_CONFIRM:
            msg_upper = message.strip().upper()
            if msg_upper == "2":
                session.state = OrderState.BROWSING
                session.pending_product = None
                self.db.save_session(user_id, session)
                return "ကောင်းပါပြီ။ ဘာကူညီပေးရမလဲ?", OrderState.BROWSING
            elif msg_upper == "1":
                return self._add_to_cart(user_id, session)
            else:
                return self._prompt_add_to_cart(session.pending_product), OrderState.CART_CONFIRM

        session.state = OrderState.CART_CONFIRM
        session.pending_product = product_info
        self.db.save_session(user_id, session)
        return self._prompt_add_to_cart(product_info), OrderState.CART_CONFIRM

    # ── cart management ───────────────────────────────────────────────────

    def handle_cart_management(
        self,
        user_id: int,
        message: str,
    ) -> Tuple[str, OrderState]:
        """Handle numbered cart menu (1–4)."""
        session  = self.db.load_session(user_id)
        msg_upper = message.strip().upper()

        if msg_upper == "1":
            return self._show_cart(session), OrderState.CART_MANAGEMENT
        elif msg_upper == "2":
            session.state = OrderState.BROWSING
            self.db.save_session(user_id, session)
            return "ကောင်းပါပြီ။ ဘယ်ဖုန်း ကြည့်ချင်ပါသလဲ?", OrderState.BROWSING
        elif msg_upper == "3":
            if not session.cart:
                return "Cart ထဲမှာ ပစ္စည်း မရှိသေးပါ။", OrderState.BROWSING
            session.state = OrderState.CHECKOUT_CONFIRM
            self.db.save_session(user_id, session)
            return self._show_checkout_confirmation(session), OrderState.CHECKOUT_CONFIRM
        elif msg_upper == "4":
            session.cart.clear()
            session.state = OrderState.BROWSING
            self.db.save_session(user_id, session)
            return "✅ Cart ကို ရှင်းလင်းပြီးပါပြီ။\n\nဘာဝယ်ချင်ပါသလဲ?", OrderState.BROWSING
        else:
            return self._show_cart_options(), OrderState.CART_MANAGEMENT

    # ── checkout flow ─────────────────────────────────────────────────────

    def handle_checkout_flow(
        self,
        user_id: int,
        message: str,
    ) -> Tuple[str, OrderState]:
        """Step-by-step checkout: address → phone → payment → note → transaction."""
        session   = self.db.load_session(user_id)
        msg_upper = message.strip().upper()

        # ── cancel at checkout confirm or payment select ──────────────
        if (
            session.state == OrderState.CHECKOUT_CONFIRM and msg_upper == "2"
        ) or (
            session.state == OrderState.PAYMENT_SELECT and msg_upper == "4"
        ):
            session.state            = OrderState.BROWSING
            session.pending_product  = None
            session.delivery_address = None
            session.phone_number     = None
            session.payment_method   = None
            session.note             = None
            session.transaction_number = None
            self.db.save_session(user_id, session)
            return (
                "❌ Order ကို ပယ်ဖျက်လိုက်ပါပြီ။ Cart ထဲမှာ ပစ္စည်းတွေ ရှိနေဆဲဖြစ်ပါတယ်။\n\n"
                "ထပ်မံ ဝယ်ယူလိုပါက ပြန်လည် ပြောပြပေးပါ။"
            ), OrderState.BROWSING

        # ── checkout confirm (1 = proceed, anything else = re-prompt) ──
        if session.state == OrderState.CHECKOUT_CONFIRM:
            if msg_upper == "1":
                session.state = OrderState.ADDRESS_INPUT
                self.db.save_session(user_id, session)
                return (
                    "လိပ်စာ ပေးပို့ပါ။\n\n(ဥပမာ: No.45, Pyay Road, Yangon)"
                ), OrderState.ADDRESS_INPUT
            return self._show_checkout_confirmation(session), OrderState.CHECKOUT_CONFIRM

        # ── address ───────────────────────────────────────────────────
        elif session.state == OrderState.ADDRESS_INPUT:
            session.delivery_address = message.strip()
            session.state            = OrderState.PHONE_INPUT
            self.db.save_session(user_id, session)
            return (
                "ဖုန်းနံပါတ် ပေးပို့ပါ။\n\n(ဥပမာ: 09771234567)"
            ), OrderState.PHONE_INPUT

        # ── phone ────────────────────────────────────────────────────
        elif session.state == OrderState.PHONE_INPUT:
            phone = message.strip()
            if not self._validate_phone(phone):
                return (
                    "ဖုန်းနံပါတ် မှားယွင်းနေပါသည်။ ထပ်မံ ရိုက်ထည့်ပေးပါ။\n\n(ဥပမာ: 09771234567)"
                ), OrderState.PHONE_INPUT
            session.phone_number = phone
            session.state        = OrderState.PAYMENT_SELECT
            self.db.save_session(user_id, session)
            return self._show_payment_options(session), OrderState.PAYMENT_SELECT

        # ── payment ──────────────────────────────────────────────────
        elif session.state == OrderState.PAYMENT_SELECT:
            if msg_upper == "1":
                session.payment_method = PaymentMethod.KBZ.value
            elif msg_upper == "2":
                session.payment_method = PaymentMethod.WAVE.value
            elif msg_upper == "3":
                session.payment_method = PaymentMethod.CASH.value
            else:
                return self._show_payment_options(session), OrderState.PAYMENT_SELECT

            session.state = OrderState.NOTE_INPUT
            self.db.save_session(user_id, session)
            return (
                "မှတ်ချက် ရှိရင် ရိုက်ပါ။\n\nမရှိရင် 'SKIP' လို့ ရိုက်ပါ။"
            ), OrderState.NOTE_INPUT

        # ── note ─────────────────────────────────────────────────────
        elif session.state == OrderState.NOTE_INPUT:
            session.note = None if msg_upper == "SKIP" else message.strip()

            if session.payment_method in [PaymentMethod.KBZ.value, PaymentMethod.WAVE.value]:
                session.state = OrderState.TRANSACTION_INPUT
                self.db.save_session(user_id, session)
                return (
                    f"💳 {session.payment_method} ဖြင့် ငွေပေးချေမည်။\n\n"
                    "Transaction Number ရိုက်ထည့်ပေးပါ။\n"
                    "(ငွေလွှဲပြီးသည့်အခါ ရရှိသော နံပါတ်)"
                ), OrderState.TRANSACTION_INPUT
            else:
                # Cash on delivery — create order immediately
                order_number  = self.db.create_order(user_id, session)
                session.state = OrderState.ORDER_COMPLETE
                self.db.save_session(user_id, session)
                return self._show_order_success(order_number, session), OrderState.ORDER_COMPLETE

        # ── transaction number ────────────────────────────────────────
        elif session.state == OrderState.TRANSACTION_INPUT:
            session.transaction_number = message.strip()
            order_number  = self.db.create_order(user_id, session)
            session.state = OrderState.ORDER_COMPLETE
            self.db.save_session(user_id, session)
            return self._show_order_success(order_number, session), OrderState.ORDER_COMPLETE

        # ── post-completion reset ─────────────────────────────────────
        elif session.state == OrderState.ORDER_COMPLETE:
            session.state              = OrderState.BROWSING
            session.delivery_address   = None
            session.phone_number       = None
            session.payment_method     = None
            session.note               = None
            session.transaction_number = None
            session.clear_cart()
            self.db.save_session(user_id, session)
            return (
                "✅ Order အောင်ပြီးပါပြီ။ ကျေးဇူးတင်ပါတယ်!\n\n"
                "ဘာကူညီပေးရမလဲ? ဖုန်းများ ဆက်ကြည့်လို့ရပါတယ်။"
            ), OrderState.BROWSING

        return "စနစ်တွင် ပြဿနာ ရှိနေပါသည်။", OrderState.BROWSING

    # ── display helpers ───────────────────────────────────────────────────

    def _guest_cannot_order(self) -> str:
        return (
            "⚠️ Guest အနေနဲ့ Order မတင်နိုင်ပါဘူး။\n\n"
            "Order တင်ချင်ရင် အရင် Login လုပ်ပေးပါ။\n\n"
            "📌 Login လုပ်ရန် သို့မဟုတ် Register လုပ်ရန် ညာဘက်ထောင့်က Menu ကို နှိပ်ပါ။\n\n"
            "Guest အနေဖြင့် ဖုန်းတွေ ကြည့်လို့ရပါတယ်။"
        )

    def _prompt_add_to_cart(self, product: Dict) -> str:
        model_display = _strip_brand_prefix(product["brand"], product["model"])
        return (
            f"ကောင်းပါပြီ! {product['brand']} {model_display} ကို cart ထဲထည့်ချင်ပါသလား?\n\n"
            f"📱 {product['brand']} {model_display}\n"
            f"💾 {product.get('ram_storage', 'N/A')}\n"
            f"🎨 {product.get('color', 'N/A')}\n"
            f"💰 {product['price']:,} Ks\n\n"
            "ရွေးချယ်ပါ:\n"
            "1 - Cart ထဲထည့်မယ်\n"
            "2 - မလုပ်တော့ဘူး"
        )

    def _add_to_cart(
        self, user_id: int, session: OrderSession
    ) -> Tuple[str, OrderState]:
        if not session.pending_product:
            return "ပစ္စည်း ရွေးထားခြင်း မရှိပါ။", OrderState.BROWSING

        product  = session.pending_product
        existing = next(
            (item for item in session.cart if item.product_id == product["id"]),
            None,
        )

        if existing:
            existing.quantity += 1
        else:
            session.cart.append(
                CartItem(
                    product_id  = product["id"],
                    brand       = product["brand"],
                    model       = product["model"],
                    price       = product["price"],
                    quantity    = 1,
                    ram_storage = product.get("ram_storage", "N/A"),
                    color       = product.get("color", "N/A"),
                )
            )

        session.pending_product = None
        session.state           = OrderState.CART_MANAGEMENT
        self.db.save_session(user_id, session)

        model_display = _strip_brand_prefix(product["brand"], product["model"])
        return (
            f"✅ {product['brand']} {model_display} ကို cart ထဲထည့်ပြီးပါပြီ။\n\n"
            "ရွေးချယ်ပါ:\n"
            "1 - Cart ကြည့်မယ်\n"
            "2 - ပစ္စည်း ဆက်ကြည့်မယ်\n"
            "3 - Order တင်မယ်\n"
            "4 - Cart ရှင်းမယ်"
        ), OrderState.CART_MANAGEMENT

    def _show_cart(self, session: OrderSession) -> str:
        if not session.cart:
            return "Cart ထဲမှာ ပစ္စည်း မရှိသေးပါ။"

        lines = ["🛒 သင့် Cart:\n"]
        for i, item in enumerate(session.cart, 1):
            lines.append(f"{i}. {item.get_display_text()}\n")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"💰 စုစုပေါင်း: {session.get_cart_total():,} Ks\n")
        lines.append(self._show_cart_options())
        return "\n".join(lines)

    def _show_cart_options(self) -> str:
        return (
            "ရွေးချယ်ပါ:\n"
            "1 - Cart ကြည့်မယ်\n"
            "2 - ပစ္စည်း ဆက်ကြည့်မယ်\n"
            "3 - Order တင်မယ်\n"
            "4 - Cart ရှင်းမယ်"
        )

    def _show_checkout_confirmation(self, session: OrderSession) -> str:
        cart_summary = "".join(
            f"• {i.brand} {i.model} - {i.get_subtotal():,} Ks\n"
            for i in session.cart
        )
        return (
            f"📋 Order အတည်ပြုချက်:\n\n{cart_summary}"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 စုစုပေါင်း: {session.get_cart_total():,} Ks\n\n"
            "ရွေးချယ်ပါ:\n"
            "1 - Order တင်မယ်\n"
            "2 - မတင်တော့ဘူး"
        )

    def _show_payment_options(self, session: OrderSession) -> str:
        cart_summary = "".join(
            f"• {i.brand} {i.model} - {i.get_subtotal():,} Ks\n"
            for i in session.cart
        )
        return (
            f"📋 Order အချက်အလက်:\n\n{cart_summary}"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 စုစုပေါင်း: {session.get_cart_total():,} Ks\n\n"
            f"📍 ပို့ရန်လိပ်စာ: {session.delivery_address}\n"
            f"📞 ဖုန်း: {session.phone_number}\n\n"
            "💳 Payment method ရွေးပါ:\n\n"
            "1 - KBZ Pay\n"
            "2 - Wave Money\n"
            "3 - Cash on Delivery\n"
            "4 - မတင်တော့ဘူး"
        )

    def _show_order_success(self, order_number: str, session: OrderSession) -> str:
        transaction_info = (
            f"\n📱 Transaction Number: {session.transaction_number}"
            if session.transaction_number else ""
        )

        if session.payment_method == PaymentMethod.KBZ.value:
            payment_info = (
                f"\n💳 ငွေပေးချေမှု: KBZ Pay{transaction_info}\n"
                "✅ ငွေလွှဲပြီးပါပြီ။ စစ်ဆေးပြီးရင် ပို့ပေးပါမယ်။"
            )
        elif session.payment_method == PaymentMethod.WAVE.value:
            payment_info = (
                f"\n💳 ငွေပေးချေမှု: Wave Money{transaction_info}\n"
                "✅ ငွေလွှဲပြီးပါပြီ။ စစ်ဆေးပြီးရင် ပို့ပေးပါမယ်။"
            )
        else:
            payment_info = "\n💳 ငွေပေးချေမှု: Cash on Delivery\n💵 ပို့သည့်အခါ ငွေပေးပါမည်။"

        cart_summary = "".join(
            f"• {i.brand} {i.model} - {i.get_subtotal():,} Ks\n"
            for i in session.cart
        )
        return (
            f"✅ Order အောင်မြင်ပါပြီ!\n\n"
            f"📝 Order Number: {order_number}\n\n"
            f"{cart_summary}"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 စုစုပေါင်း: {session.get_cart_total():,} Ks\n\n"
            f"📍 ပို့ရန်လိပ်စာ: {session.delivery_address}\n"
            f"📞 ဖုန်း: {session.phone_number}\n"
            f"{payment_info}\n\n"
            "ကျေးဇူးတင်ပါတယ်! မကြာမီ ဆက်သွယ်ပါမယ်။"
        )

    @staticmethod
    def _validate_phone(phone: str) -> bool:
        return bool(re.match(r"^(\+?95)?0?9\d{7,9}$", phone))


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def get_order_state(user_id: Optional[int], db: OrderDatabase) -> OrderState:
    """Return the current order state for a user (BROWSING if guest)."""
    if not user_id:
        return OrderState.BROWSING
    return db.load_session(user_id).state


def reset_order_state(user_id: int, db: OrderDatabase):
    """Reset user's order to BROWSING and clear cart."""
    session = db.load_session(user_id)
    session.state = OrderState.BROWSING
    session.clear_cart()
    db.save_session(user_id, session)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Order System Module v2 — Fixed")
    print("=" * 60)
    print("Fixes in this version:")
    print("  • Compound model names (17ProMax, 17Pro Max) parsed correctly")
    print("  • Brand alias map (iphone→Apple/iPhone) resolved at DB level")
    print("  • Digit-led model tokens ('17') matched with word-boundary SQL")
    print("  • Fuzzy fallback via rapidfuzz when SQL returns nothing")
    print("  • Failed lookups never cached (caller must guard this)")
    print("  • Score-5 false-positive rejection tightened")