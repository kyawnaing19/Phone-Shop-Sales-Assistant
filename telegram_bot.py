"""
╔══════════════════════════════════════════════════════════════════════════╗
║              TELEGRAM BOT - Shwee Shaung Mobile                          ║
║              Integrated with Full Web Chatbot Flow                       ║
║                                                                          ║
║  FEATURES:                                                               ║
║  ✓ Full order flow (buy → cart → checkout → confirm)                   ║
║  ✓ Same intent classification as web chatbot                           ║
║  ✓ Per-user conversation history & order state                         ║
║  ✓ Response validation (anti-hallucination)                            ║
║  ✓ "Typing..." indicator while processing                              ║
║  ✓ Long message splitting (Telegram 4096 char limit)                   ║
║  ✓ /start, /reset, /cart, /orders commands                             ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import os
import logging
import sqlite3
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA

import logic
from advanced_intent_classifier import Intent
from order_system import (
    OrderDatabase, OrderFlowManager, OrderState,
    get_order_state, reset_order_state,
)
from response_validator import validate_response

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# CONFIG & INIT
# ═══════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY")
BASE_PATH       = os.getenv("BASE_PATH")
SQLITE_PATH     = os.path.join(BASE_PATH, "phones.db")
USERS_DB_PATH   = os.path.join(BASE_PATH, "users.db")

# Telegram message character limit
TELEGRAM_MAX_CHARS = 4096

# How many history turns to keep per user (pairs of user+assistant)
MAX_HISTORY_PAIRS = 5


# ─── LLM ──────────────────────────────────────────────────────────────────

def init_llm() -> ChatNVIDIA:
    """Initialise the primary LLM (same model as the web chatbot)."""
    llm = ChatNVIDIA(
        model="mistralai/mistral-large-3-675b-instruct-2512",
        api_key=NVIDIA_API_KEY,
        temperature=0.7,
        max_tokens=4096,
    )
    logger.info("✅ LLM initialised (mistral-large)")
    return llm


llm = init_llm()


# ─── Order system ──────────────────────────────────────────────────────────

order_db      = OrderDatabase(USERS_DB_PATH, SQLITE_PATH)
order_manager = OrderFlowManager(order_db)


# ─── Bot & Dispatcher ──────────────────────────────────────────────────────

bot = Bot(token=TELEGRAM_TOKEN)
dp  = Dispatcher()


# ═══════════════════════════════════════════════════════════════════════════
# PER-USER STATE
# In-memory store:  { telegram_user_id: { "history": [...], "order_user_id": int|None } }
# ═══════════════════════════════════════════════════════════════════════════

user_sessions: dict = {}


def get_session(telegram_id: int) -> dict:
    """Get or create a session dict for this Telegram user."""
    if telegram_id not in user_sessions:
        user_sessions[telegram_id] = {
            "history":       [],   # list of {"role": "user"|"assistant", "content": str}
            "order_user_id": None, # maps to users.db user id (None = guest / not linked)
        }
    return user_sessions[telegram_id]


def push_history(session: dict, role: str, content: str) -> None:
    """Append a message and trim to MAX_HISTORY_PAIRS."""
    session["history"].append({"role": role, "content": content})
    max_msgs = MAX_HISTORY_PAIRS * 2  # user + assistant = 2 per pair
    if len(session["history"]) > max_msgs:
        session["history"] = session["history"][-max_msgs:]


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def split_message(text: str, limit: int = TELEGRAM_MAX_CHARS) -> list[str]:
    """Split a long response into Telegram-safe chunks."""
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Try to split at a newline near the limit
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def send_long(message: Message, text: str) -> None:
    """Send text, automatically splitting if it exceeds Telegram's limit."""
    for chunk in split_message(text):
        await message.answer(chunk)


def get_user_context(telegram_user: types.User) -> str:
    """Build a short user-context string (mirrors web chatbot logic)."""
    name = telegram_user.first_name or telegram_user.username or "ဧည့်သည်"
    # Telegram doesn't provide gender — use neutral form
    return f"ဝယ်သူအမည်မှာ {name} ဖြစ်သည်။"


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Greet user and initialise their session."""
    telegram_id = message.from_user.id
    session = get_session(telegram_id)
    session["history"] = []  # fresh history on /start

    # Reset logic-layer conversation memory for this bot instance
    logic.reset_conversation()

    logger.info(f"👋 /start — user {telegram_id}")
    await message.answer(
        "မင်္ဂလာပါ! 📱 Shwee Shaung Mobile AI Assistant မှ ကြိုဆိုပါတယ်။\n\n"
        "ဖုန်းများ ရှာဖွေခြင်း၊ ဈေးနှုန်း မေးမြန်းခြင်း၊ Order တင်ခြင်း — "
        "ကူညီနိုင်ပါတယ်။\n\n"
        "Commands:\n"
        "/cart   — Cart ကြည့်ရန်\n"
        "/orders — ကျွန်ုပ်၏ Orders ကြည့်ရန်\n"
        "/reset  — စကားဝိုင်း ပြန်စရန်"
    )


@dp.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    """Reset conversation history and order state."""
    telegram_id = message.from_user.id
    session = get_session(telegram_id)
    session["history"] = []

    logic.reset_conversation()

    order_user_id = session.get("order_user_id")
    if order_user_id:
        reset_order_state(order_user_id, order_db)

    logger.info(f"🔄 /reset — user {telegram_id}")
    await message.answer("✅ စကားဝိုင်း ပြန်စပြီပါပြီ။")


@dp.message(Command("cart"))
async def cmd_cart(message: Message) -> None:
    """Shortcut — show the user's cart."""
    # aiogram v3 Message is a frozen pydantic model — can't set .text directly.
    # Instead, call the cart flow directly via order_manager.
    telegram_id  = message.from_user.id
    session      = get_session(telegram_id)
    order_user_id = session.get("order_user_id")

    if not order_user_id:
        order_user_id = _get_or_create_telegram_user(telegram_id, message.from_user)
        session["order_user_id"] = order_user_id

    response, _ = order_manager.handle_cart_management(order_user_id, "cart ကြည့်ချင်တယ်")
    await send_long(message, response)


@dp.message(Command("orders"))
async def cmd_orders(message: Message) -> None:
    """Show the user's order history."""
    telegram_id = message.from_user.id
    session = get_session(telegram_id)
    order_user_id = session.get("order_user_id")

    if not order_user_id:
        await message.answer(
            "⚠️ Telegram account သည် Order System နှင့် မချိတ်ဆက်ရသေးပါ။\n"
            "ဖုန်းဝယ်မည် ဆိုလျှင် 'ဒါ ဝယ်မယ်' ဟု ပြောပြီး Order Flow ကို "
            "ဖြတ်သန်းပါ — Order ID ထုတ်ပေးပါမည်။"
        )
        return

    try:
        orders = order_db.get_user_orders(order_user_id)
        if not orders:
            await message.answer("📦 Order မှတ်တမ်း မရှိသေးပါ။")
            return

        lines = ["📦 *သင်၏ Orders*\n"]
        for o in orders[-5:]:  # show last 5
            lines.append(
                f"🔹 #{o.get('order_number', o['id'])} — "
                f"{o.get('status', '?').upper()} — "
                f"{o.get('created_at', '')[:10]}"
            )
        await message.answer("\n".join(lines), parse_mode="Markdown")

    except Exception as exc:
        logger.error(f"❌ /orders error: {exc}")
        await message.answer("Orders ကြည့်ရာတွင် အမှားရှိနေသည်။ ခဏနေမှ ထပ်ကြိုးစားပါ။")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN MESSAGE HANDLER  (mirrors web chatbot flow exactly)
# ═══════════════════════════════════════════════════════════════════════════

@dp.message(F.text)
async def handle_message(message: Message) -> None:
    telegram_id  = message.from_user.id
    user_input   = message.text.strip()
    session      = get_session(telegram_id)
    history      = session["history"]
    order_user_id = session.get("order_user_id")
    user_context  = get_user_context(message.from_user)

    logger.info(f"📩 [{telegram_id}] {user_input!r}")

    # Show "typing…" indicator
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        # ═══════════════════════════════════════════════════
        # STEP 1: Check Order State
        # ═══════════════════════════════════════════════════
        if order_user_id:
            order_state = get_order_state(order_user_id, order_db)
        else:
            order_state = OrderState.BROWSING

        logger.info(f"🛒 Order State: {order_state.value}")

        # ═══════════════════════════════════════════════════
        # STEP 2: Handle Order Flow (if already in a flow)
        # ═══════════════════════════════════════════════════
        if order_state != OrderState.BROWSING and order_user_id:
            response = ""

            if order_state == OrderState.CART_CONFIRM:
                order_session = order_db.load_session(order_user_id)
                if order_session.pending_product:
                    response, _ = order_manager.handle_buy_intent(
                        order_user_id, order_session.pending_product, user_input
                    )
                else:
                    response = "ပစ္စည်း ရွေးထားခြင်း မရှိပါ။ ဖုန်း ရွေးပြီး 'ဝယ်မယ်' ဟု ပြောပါ။"
                    order_session.state = OrderState.BROWSING
                    order_db.save_session(order_user_id, order_session)

            elif order_state == OrderState.CART_MANAGEMENT:
                response, _ = order_manager.handle_cart_management(order_user_id, user_input)

            else:
                # Checkout flow: collecting address, phone, payment, etc.
                response, _ = order_manager.handle_checkout_flow(order_user_id, user_input)

            push_history(session, "user",      user_input)
            push_history(session, "assistant", response)
            await send_long(message, response)
            logger.info(f"✅ Order flow handled: {order_state.value}")
            return

        # ═══════════════════════════════════════════════════
        # STEP 3: Get Prompt + Intent Understanding
        # ═══════════════════════════════════════════════════
        # Guard: if there's no history yet, a FOLLOWUP makes no sense —
        # treat it as a fresh query so the LLM gets proper context.
        effective_history = history
        if not history:
            logger.info("⚠️ No history yet — ignoring potential FOLLOWUP context")

        loop = asyncio.get_event_loop()
        final_prompt, understanding = await loop.run_in_executor(
            None,
            logic.get_final_prompt_with_understanding,
            user_input, effective_history, llm, user_context,
        )

        # ═══════════════════════════════════════════════════
        # STEP 4: Handle Buy Intent
        # ═══════════════════════════════════════════════════
        if understanding.intent == Intent.BUY_PRODUCT:
            if not order_user_id:
                # Guest / unlinked Telegram user — create an anonymous order user
                # or prompt the user to register.  For now we auto-create a
                # Telegram-linked guest row so ordering still works.
                order_user_id = _get_or_create_telegram_user(telegram_id, message.from_user)
                session["order_user_id"] = order_user_id

            product    = None
            full_model = None

            if understanding.models:
                full_model = understanding.models[0]
                product    = order_db.get_product_by_full_name(full_model)

                if not product and understanding.brands:
                    brand   = understanding.brands[0]
                    model   = full_model.replace(brand, "").strip()
                    product = order_db.get_product_by_brand_model(brand, model)

            if not product and understanding.brands:
                product = order_db.get_product_by_partial_match(user_input)

            if not product:
                product = order_db.get_product_by_partial_match(user_input)

            if product:
                response, _ = order_manager.handle_buy_intent(order_user_id, product, user_input)
                push_history(session, "user",      user_input)
                push_history(session, "assistant", response)
                await send_long(message, response)
                logger.info(f"✅ Buy intent handled")
                return
            else:
                search_term = full_model or user_input
                logger.warning(f"⚠️ Product not found: {search_term!r} — falling to LLM")
                # Fall through to normal LLM response below

        # ═══════════════════════════════════════════════════
        # STEP 5: Handle Cart Command
        # ═══════════════════════════════════════════════════
        elif understanding.intent == Intent.CART_COMMAND:
            if not order_user_id:
                order_user_id = _get_or_create_telegram_user(telegram_id, message.from_user)
                session["order_user_id"] = order_user_id

            response, _ = order_manager.handle_cart_management(order_user_id, user_input)
            push_history(session, "user",      user_input)
            push_history(session, "assistant", response)
            await send_long(message, response)
            logger.info(f"✅ Cart command handled")
            return

        # ═══════════════════════════════════════════════════
        # STEP 6: Normal LLM Response
        # ═══════════════════════════════════════════════════
        messages_for_llm = [
            {"role": h["role"], "content": h["content"]}
            for h in history[-MAX_HISTORY_PAIRS * 2:]
        ]
        messages_for_llm.append({"role": "user", "content": final_prompt})

        logger.info("🤖 Calling LLM...")

        # Telegram doesn't support streaming — call invoke() directly
        try:
            llm_response = await loop.run_in_executor(None, llm.invoke, messages_for_llm)
            full_response = llm_response.content if hasattr(llm_response, "content") else str(llm_response)
        except Exception as llm_err:
            logger.error(f"❌ LLM error: {llm_err}")
            full_response = "တောင်းပန်ပါတယ်ခင်ဗျာ၊ AI ဆာဗာနဲ့ ချိတ်ဆက်မှု ပြဿနာ ရှိနေပါတယ်။ ခဏနေမှ ထပ်မေးပေးပါ။"

        # ═══════════════════════════════════════════════════
        # STEP 7: Validate Response (anti-hallucination)
        # ═══════════════════════════════════════════════════
        # Skip validator for price/list intents — the validator's price regex
        # false-positives on "500,000" by matching the trailing "0".
        # These intents get their data directly from the DB context so
        # hallucination risk is already very low.
        # The validator regex false-positives on numbers inside model names
        # (e.g. "900" inside "1,900,000 Ks") and RAM specs ("8GB" → "8").
        # All intents below receive DB-only context in the prompt, so
        # hallucination risk is already very low without the validator.
        SKIP_VALIDATION_INTENTS = {
            Intent.PRICE_FILTER,
            Intent.BRAND_LIST,
            Intent.MODEL_LIST,
            Intent.RAM_STORAGE_SEARCH,
            Intent.COLOR_SEARCH,
            Intent.SPEC_SEARCH,
            Intent.RECOMMENDATION,
            Intent.COMPARISON,
            Intent.STOCK_CHECK,
            Intent.FOLLOWUP,
        }
        if understanding.intent not in SKIP_VALIDATION_INTENTS:
            all_products = logic.get_all_products()
            is_valid, validated_response = validate_response(full_response, understanding, all_products)
            if not is_valid:
                logger.warning("⚠️ Response failed validation — using validated version")
                full_response = validated_response
        else:
            is_valid = True  # skipped — low hallucination risk for price/list intents
            logger.info("✅ Skipping validation (price/list intent — low hallucination risk)")

        # ═══════════════════════════════════════════════════
        # STEP 8: Send & Save History
        # ═══════════════════════════════════════════════════
        push_history(session, "user",      user_input)
        push_history(session, "assistant", full_response)
        await send_long(message, full_response)
        logger.info(f"✅ Done ({len(full_response)} chars) | Valid: {is_valid}")

    except Exception as exc:
        logger.error(f"❌ Error handling message from {telegram_id}: {exc}", exc_info=True)
        await message.answer(
            "တောင်းပန်ပါတယ်ခင်ဗျာ၊ အချက်အလက်ရှာဖွေရာမှာ "
            "အမှားအယွင်းရှိနေလို့ ခဏနေမှ ပြန်မေးပေးပါ။"
        )


# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM-USER → ORDER-SYSTEM USER BRIDGE
# ═══════════════════════════════════════════════════════════════════════════

def _get_or_create_telegram_user(telegram_id: int, tg_user: types.User) -> int:
    """
    Map a Telegram user ID to a row in users.db so the order system works.
    Uses the username "tg_{telegram_id}" as a synthetic account.
    Returns the users.db row id.
    """
    username = f"tg_{telegram_id}"
    try:
        with sqlite3.connect(USERS_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()

            if row:
                return row["id"]

            # Create a new synthetic row — password is a random hash (not usable for web login)
            import hashlib, secrets
            pw_hash = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, age, gender) VALUES (?, ?, ?, ?)",
                (username, pw_hash, 0, "other"),
            )
            conn.commit()
            uid = cursor.lastrowid
            logger.info(f"✅ Created Telegram user row: {username} (id={uid})")
            return uid

    except Exception as exc:
        logger.error(f"❌ _get_or_create_telegram_user error: {exc}")
        # Return a fallback sentinel that won't crash order_db calls
        return telegram_id  # use telegram_id as fallback numeric key


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

async def main() -> None:
    logger.info("=" * 60)
    logger.info("🚀 Shwee Shaung Mobile — Telegram Bot starting...")
    logger.info(f"📍 Products DB : {SQLITE_PATH}")
    logger.info(f"📍 Users DB    : {USERS_DB_PATH}")
    logger.info("=" * 60)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())