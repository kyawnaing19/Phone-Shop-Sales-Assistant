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
║  ✓ Strict keyword confirmation system                                  ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import sqlite3
import logging
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# ORDER STATE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

class OrderState(str, Enum):
    """Order processing states"""
    BROWSING = "browsing"  # Default state - just browsing products
    CART_CONFIRM = "cart_confirm"  # Asking if user wants to add to cart
    CART_MANAGEMENT = "cart_management"  # Managing cart (view, add more, checkout)
    CHECKOUT_CONFIRM = "checkout_confirm"  # Confirming order before address
    ADDRESS_INPUT = "address_input"  # Waiting for delivery address
    PHONE_INPUT = "phone_input"  # Waiting for phone number
    PAYMENT_SELECT = "payment_select"  # Selecting payment method
    NOTE_INPUT = "note_input"  # Optional note input
    TRANSACTION_INPUT = "transaction_input"  # Transaction number input (for digital payments)
    ORDER_COMPLETE = "order_complete"  # Order successfully placed


class PaymentMethod(str, Enum):
    """Available payment methods"""
    KBZ = "KBZ Pay"
    WAVE = "Wave Money"
    CASH = "Cash on Delivery"


# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CartItem:
    """Single item in shopping cart"""
    product_id: int
    brand: str
    model: str
    price: int
    quantity: int
    ram_storage: str
    color: str

    def to_dict(self) -> Dict:
        return asdict(self)

    def get_subtotal(self) -> int:
        return self.price * self.quantity

    def get_display_text(self) -> str:
        """Format cart item for display"""
        return f"""📱 {self.brand} {self.model}
💾 {self.ram_storage}
🎨 {self.color}
💰 {self.price:,} Ks x {self.quantity}
   = {self.get_subtotal():,} Ks"""


@dataclass
class OrderSession:
    """User's current ordering session"""
    user_id: Optional[int] = None
    state: OrderState = OrderState.BROWSING
    cart: List[CartItem] = field(default_factory=list)
    pending_product: Optional[Dict] = None  # Product waiting for confirmation

    # Order details being collected
    delivery_address: Optional[str] = None
    phone_number: Optional[str] = None
    payment_method: Optional[str] = None
    note: Optional[str] = None
    transaction_number: Optional[str] = None  # For digital payment transactions

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "state": self.state.value,
            "cart": [item.to_dict() for item in self.cart],
            "pending_product": self.pending_product,
            "delivery_address": self.delivery_address,
            "phone_number": self.phone_number,
            "payment_method": self.payment_method,
            "note": self.note,
            "transaction_number": self.transaction_number
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'OrderSession':
        """Reconstruct OrderSession from dict"""
        cart_items = [CartItem(**item) for item in data.get('cart', [])]
        return cls(
            user_id=data.get('user_id'),
            state=OrderState(data.get('state', 'browsing')),
            cart=cart_items,
            pending_product=data.get('pending_product'),
            delivery_address=data.get('delivery_address'),
            phone_number=data.get('phone_number'),
            payment_method=data.get('payment_method'),
            note=data.get('note'),
            transaction_number=data.get('transaction_number')
        )

    def get_cart_total(self) -> int:
        """Calculate total cart value"""
        return sum(item.get_subtotal() for item in self.cart)

    def get_cart_count(self) -> int:
        """Get total number of items in cart"""
        return sum(item.quantity for item in self.cart)

    def clear_cart(self):
        """Empty the cart"""
        self.cart = []
        self.pending_product = None


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════

class OrderDatabase:
    """Handle all database operations for orders"""

    def __init__(self, db_path: str, products_db_path: str):
        self.db_path = db_path
        self.products_db_path = products_db_path
        self._init_tables()

    @contextmanager
    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _get_products_connection(self):
        """Get products database connection"""
        conn = sqlite3.connect(self.products_db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_tables(self):
        """Initialize order tables"""
        with self._get_connection() as conn:
            # Check if tables exist and migrate if needed
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='orders'
            """)
            table_exists = cursor.fetchone() is not None

            if table_exists:
                # Check if columns exist
                cursor = conn.execute("PRAGMA table_info(orders)")
                columns = [row[1] for row in cursor.fetchall()]

                # Check for missing columns
                needs_migration = False
                if 'order_number' not in columns:
                    logger.warning("⚠️ Migrating orders table - adding order_number column")
                    needs_migration = True
                if 'transaction_number' not in columns:
                    logger.warning("⚠️ Migrating orders table - adding transaction_number column")
                    needs_migration = True

                if needs_migration:
                    # Drop and recreate tables
                    conn.execute("DROP TABLE IF EXISTS order_items")
                    conn.execute("DROP TABLE IF EXISTS orders")

            # Orders table (with transaction_number)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_number TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    total_amount INTEGER NOT NULL,
                    delivery_address TEXT NOT NULL,
                    phone_number TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    note TEXT,
                    transaction_number TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)

            # Order items table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    brand TEXT NOT NULL,
                    model TEXT NOT NULL,
                    ram_storage TEXT NOT NULL,
                    color TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
                )
            """)

            # Order state sessions (temporary storage during checkout)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS order_sessions (
                    user_id INTEGER PRIMARY KEY,
                    session_data TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)

            conn.commit()

        logger.info("✅ Order tables initialized")

    def get_product_by_brand_model(self, brand: str, model: str) -> Optional[Dict]:
        """Get product from database by brand and model"""
        with self._get_products_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM products 
                WHERE LOWER(brand) = LOWER(?) AND LOWER(model) = LOWER(?)
                LIMIT 1
            """, (brand, model))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_product_by_full_name(self, full_name: str) -> Optional[Dict]:
        """Get product by searching full name (brand + model)

        This handles cases like "iPhone 17 Pro Max" where we need to match
        against brand='iPhone' and model='17 Pro Max'
        """
        with self._get_products_connection() as conn:
            # Try exact match first
            cursor = conn.execute("""
                SELECT * FROM products 
                WHERE LOWER(brand || ' ' || model) = LOWER(?)
                LIMIT 1
            """, (full_name,))
            row = cursor.fetchone()

            if row:
                return dict(row)

            # Try partial match (contains)
            cursor = conn.execute("""
                SELECT * FROM products 
                WHERE LOWER(brand || ' ' || model) LIKE LOWER(?)
                ORDER BY 
                    CASE 
                        WHEN LOWER(brand || ' ' || model) = LOWER(?) THEN 1
                        WHEN LOWER(brand || ' ' || model) LIKE LOWER(?) THEN 2
                        ELSE 3
                    END
                LIMIT 1
            """, (f'%{full_name}%', full_name, f'{full_name}%'))
            row = cursor.fetchone()

            return dict(row) if row else None

    def get_product_by_partial_match(self, search_text: str) -> Optional[Dict]:
        """Search for product by partial match with smart model number extraction

        Prioritizes exact model number matches over partial text matches.

        Examples:
        - "xiaomi 15" → finds "Xiaomi 15 Pro" (not "Xiaomi Civi 3")
        - "i want to buy xiaomi 15" → extracts "xiaomi 15", finds "Xiaomi 15 Pro"
        - "samsung s24 ultra" → finds "Samsung Galaxy S24 Ultra"
        """
        import re

        with self._get_products_connection() as conn:
            search_lower = search_text.lower().strip()

            # Extract model numbers and identifiers with improved precision
            # Use word boundaries to match standalone numbers only
            model_patterns = [
                r'\b([a-z]\d+[a-z]*)\b',  # s24, v60, x6 (letter+number combos)
                r'\b(\d+)\b',              # 15, 17, 13 (standalone numbers ONLY - won't match "1" in "17")
                r'\b([a-z]+\s+\d+)\b'      # note 13, civi 3 (phrase + number)
            ]

            model_identifiers = []
            for pattern in model_patterns:
                matches = re.findall(pattern, search_lower)
                model_identifiers.extend(matches)

            # Remove duplicates while preserving order
            seen = set()
            model_identifiers = [x for x in model_identifiers if not (x in seen or seen.add(x))]

            # Extract brand name (common brands)
            brands_in_db = [
                'xiaomi', 'samsung', 'iphone', 'apple', 'vivo', 'oppo', 'realme',
                'redmi', 'poco', 'oneplus', 'google', 'pixel', 'nokia', 'tecno', 'itel'
            ]

            found_brand = None
            for brand in brands_in_db:
                if brand in search_lower:
                    found_brand = brand
                    break

            # Build smart query
            if model_identifiers:
                # We have model identifiers - prioritize exact model number matches
                model_id = model_identifiers[0].strip()  # Use first identifier found

                logger.info(f"🔍 Extracted: brand='{found_brand}', model_id='{model_id}'")

                if found_brand:
                    # Search with both brand and model number using exact word boundaries
                    # This ensures "17" matches "17 Pro" but NOT "13" or "173"
                    cursor = conn.execute("""
                        SELECT *, 
                            (CASE 
                                -- Exact model match
                                WHEN LOWER(brand) = ? AND LOWER(model) = ? THEN 1
                                -- Model starts with number + space (e.g., "17 Pro")
                                WHEN LOWER(brand) = ? AND LOWER(model) LIKE ? THEN 2
                                -- Model ends with space + number (e.g., "iPhone 17")
                                WHEN LOWER(brand) = ? AND LOWER(model) LIKE ? THEN 3
                                -- Model has number surrounded by spaces (e.g., "Note 17 Pro")
                                WHEN LOWER(brand) = ? AND LOWER(model) LIKE ? THEN 4
                                -- Fallback: contains (for partial matches)
                                WHEN LOWER(brand) = ? AND LOWER(model) LIKE ? THEN 5
                                -- Full name match
                                WHEN LOWER(brand || ' ' || model) LIKE ? THEN 6
                                ELSE 7
                            END) as score
                        FROM products 
                        WHERE LOWER(brand) = ?
                          AND (LOWER(model) = ? OR LOWER(model) LIKE ? OR LOWER(model) LIKE ? OR LOWER(model) LIKE ?)
                        ORDER BY score ASC, LENGTH(model) ASC
                        LIMIT 1
                    """, (
                        found_brand, model_id,              # Exact match
                        found_brand, f'{model_id} %',      # Starts: "17 Pro"
                        found_brand, f'% {model_id}',      # Ends: "iPhone 17"
                        found_brand, f'% {model_id} %',    # Middle: "Note 17 Pro"
                        found_brand, f'%{model_id}%',      # Fallback contains
                        f'%{found_brand}%{model_id}%',     # Full text
                        found_brand,                        # WHERE brand
                        model_id,                           # WHERE exact
                        f'{model_id} %',                    # WHERE starts
                        f'% {model_id}',                    # WHERE ends
                        f'% {model_id} %'                   # WHERE middle
                    ))
                else:
                    # Just model number, no brand
                    cursor = conn.execute("""
                        SELECT *, 
                            (CASE 
                                WHEN LOWER(model) LIKE ? THEN 1
                                WHEN LOWER(model) LIKE ? THEN 2
                                WHEN LOWER(model) LIKE ? THEN 3
                                ELSE 4
                            END) as score
                        FROM products 
                        WHERE LOWER(model) LIKE ? OR LOWER(model) LIKE ? OR LOWER(model) LIKE ?
                        ORDER BY score ASC, LENGTH(model) ASC
                        LIMIT 1
                    """, (
                        f'{model_id} %',
                        f'% {model_id} %',
                        f'% {model_id}',
                        f'{model_id} %',
                        f'% {model_id} %',
                        f'% {model_id}'
                    ))
            else:
                # No clear model identifier - fall back to general text search
                cursor = conn.execute("""
                    SELECT * FROM products 
                    WHERE LOWER(brand || ' ' || model) LIKE ?
                    ORDER BY LENGTH(brand || ' ' || model) ASC
                    LIMIT 1
                """, (f'%{search_lower}%',))

            row = cursor.fetchone()

            if row:
                result = dict(row)
                result.pop('score', None)
                logger.info(f"✅ Matched: {result['brand']} {result['model']}")
                return result

            logger.warning(f"❌ No match found for: {search_text}")
            return None

    def save_session(self, user_id: int, session: OrderSession):
        """Save order session to database"""
        session_json = json.dumps(session.to_dict())

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO order_sessions (user_id, session_data, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (user_id, session_json))
            conn.commit()

        logger.info(f"💾 Saved session for user {user_id}")

    def load_session(self, user_id: int) -> OrderSession:
        """Load order session from database"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT session_data FROM order_sessions WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()

        if row:
            session_dict = json.loads(row[0])
            return OrderSession.from_dict(session_dict)

        # Return new session if none exists
        return OrderSession(user_id=user_id)

    def clear_session(self, user_id: int):
        """Clear user's order session"""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM order_sessions WHERE user_id = ?", (user_id,))
            conn.commit()

    def generate_order_number(self) -> str:
        """Generate unique order number"""
        date_str = datetime.now().strftime("%Y%m%d")

        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE order_number LIKE ?
            """, (f"ORD-{date_str}-%",))
            count = cursor.fetchone()[0]

        return f"ORD-{date_str}-{count + 1:04d}"

    def create_order(self, user_id: int, session: OrderSession) -> str:
        """Create order from session"""
        order_number = self.generate_order_number()

        with self._get_connection() as conn:
            # Insert order
            cursor = conn.execute("""
                INSERT INTO orders (
                    order_number, user_id, total_amount,
                    delivery_address, phone_number, payment_method, note, transaction_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_number,
                user_id,
                session.get_cart_total(),
                session.delivery_address,
                session.phone_number,
                session.payment_method,
                session.note,
                session.transaction_number
            ))

            order_id = cursor.lastrowid

            # Insert order items
            for item in session.cart:
                conn.execute("""
                    INSERT INTO order_items (
                        order_id, product_id, brand, model,
                        ram_storage, color, price, quantity
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order_id,
                    item.product_id,
                    item.brand,
                    item.model,
                    item.ram_storage,
                    item.color,
                    item.price,
                    item.quantity
                ))

            conn.commit()

        # Clear session after order creation
        self.clear_session(user_id)

        logger.info(f"✅ Order created: {order_number}")
        return order_number

    def get_user_orders(self, user_id: int) -> List[Dict]:
        """Get all orders for a user"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM orders 
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]


# ═══════════════════════════════════════════════════════════════════════════
# ORDER FLOW MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class OrderFlowManager:
    """Manage order flow and state transitions"""

    # Strict keywords for confirmation
    KEYWORDS = {
        "add_to_cart": "ADD TO CART",
        "view_cart": "VIEW CART",
        "add_more": "ADD MORE",
        "browse": "BROWSE",
        "checkout": "CHECKOUT",
        "confirm_order": "CONFIRM ORDER",
        "cancel": "CANCEL",
        "clear_cart": "CLEAR CART",
        "skip": "SKIP",
        "pay_kbz": "PAY KBZ",
        "pay_wave": "PAY WAVE",
        "pay_cash": "PAY CASH"
    }

    def __init__(self, db: OrderDatabase):
        self.db = db

    def is_authenticated(self, user_id: Optional[int]) -> bool:
        """Check if user is authenticated"""
        return user_id is not None

    def check_keyword(self, message: str, keyword: str) -> bool:
        """Check if message matches strict keyword"""
        return message.strip().upper() == keyword

    def handle_buy_intent(
            self,
            user_id: Optional[int],
            product_info: Dict,
            message: str
    ) -> Tuple[str, OrderState]:
        """
        Handle when user wants to buy a product

        Returns: (response_message, new_state)
        """
        # Check authentication
        if not self.is_authenticated(user_id):
            return self._guest_cannot_order(), OrderState.BROWSING

        # Load session
        session = self.db.load_session(user_id)

        # If already in cart confirmation, check for keyword
        if session.state == OrderState.CART_CONFIRM:
            # Check for CANCEL
            if self.check_keyword(message, self.KEYWORDS["cancel"]):
                session.state = OrderState.BROWSING
                session.pending_product = None
                self.db.save_session(user_id, session)
                return "ကောင်းပါပြီ။ ဘာကူညီပေးရမလဲ?", OrderState.BROWSING

            # Check for ADD TO CART
            elif self.check_keyword(message, self.KEYWORDS["add_to_cart"]):
                # Add to cart
                return self._add_to_cart(user_id, session)
            else:
                # Re-prompt for correct keyword
                return self._prompt_add_to_cart(session.pending_product), OrderState.CART_CONFIRM

        # New buy intent - store product and ask for confirmation
        session.state = OrderState.CART_CONFIRM
        session.pending_product = product_info
        self.db.save_session(user_id, session)

        return self._prompt_add_to_cart(product_info), OrderState.CART_CONFIRM

    def handle_cart_management(
            self,
            user_id: int,
            message: str
    ) -> Tuple[str, OrderState]:
        """Handle cart management commands"""
        session = self.db.load_session(user_id)

        # View cart
        if self.check_keyword(message, self.KEYWORDS["view_cart"]):
            return self._show_cart(session), OrderState.CART_MANAGEMENT

        # Browse more / Add more items (same action)
        elif self.check_keyword(message, self.KEYWORDS["browse"]) or self.check_keyword(message, self.KEYWORDS["add_more"]):
            session.state = OrderState.BROWSING
            self.db.save_session(user_id, session)
            return "ကောင်းပါပြီ။ ဘယ်ဖုန်း ကြည့်ချင်ပါသလဲ? ပြောပြပါ။", OrderState.BROWSING

        # Clear cart
        elif self.check_keyword(message, self.KEYWORDS["clear_cart"]):
            session.cart.clear()
            session.state = OrderState.BROWSING
            self.db.save_session(user_id, session)
            return "✅ Cart ကို ရှင်းလင်းပြီးပါပြီ။\n\nဘာဝယ်ချင်ပါသလဲ? ပြောပြပါ။", OrderState.BROWSING

        # Checkout
        elif self.check_keyword(message, self.KEYWORDS["checkout"]):
            if len(session.cart) == 0:
                return "Cart ထဲမှာ ပစ္စည်း မရှိသေးပါ။ ဖုန်း ရွေးပြီး 'ADD TO CART' လို့ ရိုက်ပေးပါ။", OrderState.BROWSING

            session.state = OrderState.CHECKOUT_CONFIRM
            self.db.save_session(user_id, session)
            return self._show_checkout_confirmation(session), OrderState.CHECKOUT_CONFIRM

        # Invalid command
        else:
            return self._show_cart_options(), OrderState.CART_MANAGEMENT

    def handle_checkout_flow(
            self,
            user_id: int,
            message: str
    ) -> Tuple[str, OrderState]:
        """Handle checkout process"""
        session = self.db.load_session(user_id)

        # Check for CANCEL at any stage
        if self.check_keyword(message, self.KEYWORDS["cancel"]):
            session.state = OrderState.BROWSING
            session.pending_product = None
            # Keep cart but reset checkout details
            session.delivery_address = None
            session.phone_number = None
            session.payment_method = None
            session.note = None
            session.transaction_number = None
            self.db.save_session(user_id, session)
            return "❌ Order ကို ပယ်ဖျက်လိုက်ပါပြီ။ Cart ထဲမှာ ပစ္စည်းတွေ ရှိနေဆဲဖြစ်ပါတယ်။\n\nထပ်မံ ဝယ်ယူလိုပါက ပြန်လည် ပြောပြပေးပါ။", OrderState.BROWSING

        # Checkout confirmation
        if session.state == OrderState.CHECKOUT_CONFIRM:
            if self.check_keyword(message, self.KEYWORDS["confirm_order"]):
                session.state = OrderState.ADDRESS_INPUT
                self.db.save_session(user_id, session)
                return "လိပ်စာ ပေးပို့ပါ။\n\n(ဥပမာ: No.45, Pyay Road, Yangon)\n\n• 'CANCEL' - မတင်တော့ဘူး", OrderState.ADDRESS_INPUT
            else:
                return self._show_checkout_confirmation(session), OrderState.CHECKOUT_CONFIRM

        # Address input
        elif session.state == OrderState.ADDRESS_INPUT:
            session.delivery_address = message.strip()
            session.state = OrderState.PHONE_INPUT
            self.db.save_session(user_id, session)
            return "ဖုန်းနံပါတ် ပေးပို့ပါ။\n\n(ဥပမာ: 09771234567)\n\n• 'CANCEL' - မတင်တော့ဘူး", OrderState.PHONE_INPUT

        # Phone input
        elif session.state == OrderState.PHONE_INPUT:
            phone = message.strip()
            if not self._validate_phone(phone):
                return "ဖုန်းနံပါတ် မှားယွင်းနေပါသည်။ ထပ်မံ ရိုက်ထည့်ပေးပါ။\n\n(ဥပမာ: 09771234567)\n\n• 'CANCEL' - မတင်တော့ဘူး", OrderState.PHONE_INPUT

            session.phone_number = phone
            session.state = OrderState.PAYMENT_SELECT
            self.db.save_session(user_id, session)
            return self._show_payment_options(session), OrderState.PAYMENT_SELECT

        # Payment selection
        elif session.state == OrderState.PAYMENT_SELECT:
            if self.check_keyword(message, self.KEYWORDS["pay_kbz"]):
                session.payment_method = PaymentMethod.KBZ.value
            elif self.check_keyword(message, self.KEYWORDS["pay_wave"]):
                session.payment_method = PaymentMethod.WAVE.value
            elif self.check_keyword(message, self.KEYWORDS["pay_cash"]):
                session.payment_method = PaymentMethod.CASH.value
            else:
                return self._show_payment_options(session), OrderState.PAYMENT_SELECT

            session.state = OrderState.NOTE_INPUT
            self.db.save_session(user_id, session)
            return "မှတ်ချက် ရှိရင် ရိုက်ပါ။\n\nမရှိရင် 'SKIP' လို့ ရိုက်ပါ။\n\n• 'CANCEL' - မတင်တော့ဘူး", OrderState.NOTE_INPUT

        # Note input
        elif session.state == OrderState.NOTE_INPUT:
            if self.check_keyword(message, self.KEYWORDS["skip"]):
                session.note = None
            else:
                session.note = message.strip()

            # Check if digital payment - need transaction number
            if session.payment_method in [PaymentMethod.KBZ.value, PaymentMethod.WAVE.value]:
                session.state = OrderState.TRANSACTION_INPUT
                self.db.save_session(user_id, session)
                return f"""💳 {session.payment_method} ဖြင့် ငွေပေးချေမည်။

Transaction Number ရိုက်ထည့်ပေးပါ။
(ငွေလွှဲပြီးသည့်အခါ ရရှိသော နံပါတ်)

• 'CANCEL' - မတင်တော့ဘူး""", OrderState.TRANSACTION_INPUT
            else:
                # Cash on delivery - no transaction needed, create order directly
                order_number = self.db.create_order(user_id, session)
                session.state = OrderState.ORDER_COMPLETE
                return self._show_order_success(order_number, session), OrderState.ORDER_COMPLETE

        # Transaction number input (for digital payments only)
        elif session.state == OrderState.TRANSACTION_INPUT:
            session.transaction_number = message.strip()

            # Create order
            order_number = self.db.create_order(user_id, session)
            session.state = OrderState.ORDER_COMPLETE

            return self._show_order_success(order_number, session), OrderState.ORDER_COMPLETE

        return "စနစ်တွင် ပြဿနာ ရှိနေပါသည်။", OrderState.BROWSING

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _guest_cannot_order(self) -> str:
        """Message for guests trying to order"""
        return """⚠️ Guest အနေနဲ့ Order မတင်နိုင်ပါဘူး။

Order တင်ချင်ရင် အရင် Login လုပ်ပေးပါ။

📌 Login လုပ်ရန် သို့မဟုတ် Register လုပ်ရန် ညာဘက်ထောင့်က Menu ကို နှိပ်ပါ။

Guest အနေဖြင့် ဖုန်းတွေ ကြည့်လို့ရပါတယ်။"""

    def _prompt_add_to_cart(self, product: Dict) -> str:
        """Prompt user to add product to cart"""
        return f"""ကောင်းပါပြီ! {product['brand']} {product['model']} ကို cart ထဲထည့်ချင်ပါသလား?

📱 {product['brand']} {product['model']}
💾 {product.get('ram_storage', 'N/A')}
🎨 {product.get('color', 'N/A')}
💰 {product['price']:,} Ks

• 'ADD TO CART' - Cart ထဲထည့်မယ်
• 'CANCEL' - မလုပ်တော့ဘူး"""

    def _add_to_cart(self, user_id: int, session: OrderSession) -> Tuple[str, OrderState]:
        """Add pending product to cart"""
        if not session.pending_product:
            return "ပစ္စည်း ရွေးထားခြင်း မရှိပါ။", OrderState.BROWSING

        product = session.pending_product

        # Check if product already in cart
        existing = next((item for item in session.cart
                         if item.product_id == product['id']), None)

        if existing:
            existing.quantity += 1
        else:
            cart_item = CartItem(
                product_id=product['id'],
                brand=product['brand'],
                model=product['model'],
                price=product['price'],
                quantity=1,
                ram_storage=product.get('ram_storage', 'N/A'),
                color=product.get('color', 'N/A')
            )
            session.cart.append(cart_item)

        session.pending_product = None
        session.state = OrderState.CART_MANAGEMENT
        self.db.save_session(user_id, session)

        response = f"""✅ {product['brand']} {product['model']} ကို cart ထဲထည့်ပြီးပါပြီ။

ဘာဆက်လုပ်ချင်ပါသလဲ?
• 'VIEW CART' - Cart ကြည့်မယ်
• 'BROWSE' - ဆက်ကြည့်မယ်
• 'CHECKOUT' - Order တင်မယ်"""

        return response, OrderState.CART_MANAGEMENT

    def _show_cart(self, session: OrderSession) -> str:
        """Display cart contents"""
        if len(session.cart) == 0:
            return "Cart ထဲမှာ ပစ္စည်း မရှိသေးပါ။"

        cart_text = "🛒 သင့် Cart:\n\n"

        for i, item in enumerate(session.cart, 1):
            cart_text += f"{i}. {item.get_display_text()}\n\n"

        cart_text += f"━━━━━━━━━━━━━━━━━━━━\n"
        cart_text += f"💰 စုစုပေါင်း: {session.get_cart_total():,} Ks\n\n"

        cart_text += """ဘာဆက်လုပ်ချင်ပါသလဲ?
• 'BROWSE' - ဆက်ကြည့်မယ်
• 'CHECKOUT' - Order တင်မယ်
• 'CLEAR CART' - Cart ရှင်းမယ်"""

        return cart_text

    def _show_cart_options(self) -> str:
        """Show cart management options"""
        return """ဘာလုပ်ချင်ပါသလဲ?

• 'VIEW CART' - Cart ကြည့်မယ်
• 'BROWSE' - ပစ္စည်း ဆက်ကြည့်မယ်
• 'CHECKOUT' - Order တင်မယ်
• 'CLEAR CART' - Cart ရှင်းမယ်

Keyword အတိအကျ ရိုက်ပေးပါ။"""

    def _show_checkout_confirmation(self, session: OrderSession) -> str:
        """Show checkout confirmation"""
        cart_summary = ""
        for item in session.cart:
            cart_summary += f"• {item.brand} {item.model} - {item.get_subtotal():,} Ks\n"

        return f"""📋 Order အတည်ပြုချက်:

{cart_summary}
━━━━━━━━━━━━━━━━━━━━
💰 စုစုပေါင်း: {session.get_cart_total():,} Ks

• 'CONFIRM ORDER' - Order တင်မယ်
• 'CANCEL' - မတင်တော့ဘူး"""

    def _show_payment_options(self, session: OrderSession) -> str:
        """Show payment method options with order summary"""
        # Build cart summary
        cart_summary = ""
        for item in session.cart:
            cart_summary += f"• {item.brand} {item.model} - {item.get_subtotal():,} Ks\n"

        return f"""📋 Order အချက်အလက်:

{cart_summary}
━━━━━━━━━━━━━━━━━━━━
💰 စုစုပေါင်း: {session.get_cart_total():,} Ks

📍 ပို့ရန်လိပ်စာ: {session.delivery_address}
📞 ဖုန်း: {session.phone_number}

💳 Payment method ရွေးပါ:

• 'PAY KBZ' - KBZ Pay
• 'PAY WAVE' - Wave Money
• 'PAY CASH' - Cash on Delivery
• 'CANCEL' - မတင်တော့ဘူး

Keyword အတိအကျ ရိုက်ပေးပါ။"""

    def _show_order_success(self, order_number: str, session: OrderSession) -> str:
        """Show order success message"""
        payment_info = ""

        # Show transaction number if provided (for digital payments)
        transaction_info = ""
        if session.transaction_number:
            transaction_info = f"\n📱 Transaction Number: {session.transaction_number}"

        if session.payment_method == PaymentMethod.KBZ.value:
            payment_info = f"""
💳 ငွေပေးချေမှု: KBZ Pay{transaction_info}
✅ ငွေလွှဲပြီးပါပြီ။ စစ်ဆေးပြီးရင် ပို့ပေးပါမယ်။"""

        elif session.payment_method == PaymentMethod.WAVE.value:
            payment_info = f"""
💳 ငွေပေးချေမှု: Wave Money{transaction_info}
✅ ငွေလွှဲပြီးပါပြီ။ စစ်ဆေးပြီးရင် ပို့ပေးပါမယ်။"""

        elif session.payment_method == PaymentMethod.CASH.value:
            payment_info = "\n💳 ငွေပေးချေမှု: Cash on Delivery\n💵 ပို့သည့်အခါ ငွေပေးပါမည်။"

        # Build cart summary
        cart_summary = ""
        for item in session.cart:
            cart_summary += f"• {item.brand} {item.model} - {item.get_subtotal():,} Ks\n"

        return f"""✅ Order အောင်မြင်ပါပြီ!

📝 Order Number: {order_number}

{cart_summary}
━━━━━━━━━━━━━━━━━━━━
💰 စုစုပေါင်း: {session.get_cart_total():,} Ks

📍 ပို့ရန်လိပ်စာ: {session.delivery_address}
📞 ဖုန်း: {session.phone_number}
{payment_info}

ကျေးဇူးတင်ပါတယ်! မကြာမီ ဆက်သွယ်ပါမယ်။"""


    def _validate_phone(self, phone: str) -> bool:
        """Validate Myanmar phone number"""
        import re
        # Myanmar phone: 09xxxxxxxxx or +9509xxxxxxxxx
        pattern = r'^(\+?95)?0?9\d{7,9}$'
        return bool(re.match(pattern, phone))


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def get_order_state(user_id: Optional[int], db: OrderDatabase) -> OrderState:
    """Get current order state for user"""
    if not user_id:
        return OrderState.BROWSING

    session = db.load_session(user_id)
    return session.state


def reset_order_state(user_id: int, db: OrderDatabase):
    """Reset user's order state to browsing"""
    session = db.load_session(user_id)
    session.state = OrderState.BROWSING
    session.clear_cart()
    db.save_session(user_id, session)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Order System Module")
    print("=" * 60)
    print("This module handles:")
    print("  • Shopping cart management")
    print("  • Order state flow")
    print("  • Order creation and tracking")
    print("  • User authentication checks")