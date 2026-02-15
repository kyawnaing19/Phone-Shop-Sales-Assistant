"""Myanmar Mobile Sales AI Assistant - With Ordering System"""
import asyncio
import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict

import jwt
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jwt.exceptions import InvalidTokenError
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from starlette.middleware.cors import CORSMiddleware

import logic
from advanced_intent_classifier import Intent
# Import ordering system
from order_system import (
    OrderDatabase, OrderFlowManager, OrderState,
    get_order_state, reset_order_state
)
from response_validator import validate_response
from typing import List

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Myanmar Mobile Sales AI")
templates = Jinja2Templates(directory="templates")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# JWT - WITH FALLBACK
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not os.getenv("JWT_SECRET_KEY"):
    logger.warning("⚠️ SECRET_KEY not in .env, using default (NOT SECURE FOR PRODUCTION!)")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

base_path = os.getenv("BASE_PATH")
SQLITE_PATH = os.path.join(base_path, "phones.db")
CHROMA_PATH = os.path.join(base_path, "chroma_db_v3")
USERS_DB_PATH = os.path.join(base_path, "users.db")


order_db = OrderDatabase(USERS_DB_PATH, SQLITE_PATH)
order_manager = OrderFlowManager(order_db)

# Embeddings
embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")

# Model Registry
MODEL_REGISTRY: Dict[str, ChatNVIDIA] = {}

def init_llm_models():
    nvidia_api_key = os.getenv("NVIDIA_API_KEY")
    models = {
        "mistral-large": "mistralai/mistral-large-3-675b-instruct-2512",
        "llama-3": "meta/llama-3.1-405b-instruct",
        # "deepseek-v3": "deepseek-ai/deepseek-r1"
    }
    for key, name in models.items():
        try:
            MODEL_REGISTRY[key] = ChatNVIDIA(model=name, api_key=nvidia_api_key, temperature=0.7, max_tokens=4096)
            logger.info(f"✅ Init: {key} ({name})")
        except Exception as e:
            logger.error(f"❌ Failed {key}: {e}")
    logger.info(f"✅ {len(MODEL_REGISTRY)} models ready")

init_llm_models()

def get_llm(model_type: str = "mistral-large"):
    return MODEL_REGISTRY.get(model_type, MODEL_REGISTRY.get("mistral-large"))

def get_db_conn():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_users_db_conn():
    conn = sqlite3.connect(USERS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_users_db():
    conn = get_users_db_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL, age INTEGER, gender TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_login TIMESTAMP)""")
    conn.commit()
    conn.close()
    logger.info("✅ Users DB ready")

def init_chat_history_db():
    conn = get_users_db_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS chat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        model TEXT DEFAULT 'mistral-large', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL,
        role TEXT NOT NULL, content TEXT NOT NULL, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE)""")
    conn.commit()
    conn.close()
    logger.info("✅ Chat history DB ready")

init_users_db()
init_chat_history_db()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain: str, hashed: str) -> bool:
    return hash_password(plain) == hashed

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError:
        return None

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    conn = get_users_db_conn()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return dict(user)

async def get_optional_user(request: Request):
    try:
        return await get_current_user(request)
    except:
        return None

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/api/register")
async def register_user(username: str = Form(...), password: str = Form(...), age: int = Form(...), gender: str = Form(...)):
    try:
        if len(username) < 3:
            return JSONResponse(status_code=400, content={"success": False, "message": "Username >= 3 chars"})
        if len(password) < 6:
            return JSONResponse(status_code=400, content={"success": False, "message": "Password >= 6 chars"})
        if age < 13 or age > 100:
            return JSONResponse(status_code=400, content={"success": False, "message": "Age 13-100"})
        if gender not in ["male", "female", "other"]:
            return JSONResponse(status_code=400, content={"success": False, "message": "Invalid gender"})
        conn = get_users_db_conn()
        if conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
            conn.close()
            return JSONResponse(status_code=400, content={"success": False, "message": "Username exists"})
        conn.execute("INSERT INTO users (username, password_hash, age, gender) VALUES (?, ?, ?, ?)",
                     (username, hash_password(password), age, gender))
        conn.commit()
        conn.close()
        logger.info(f"✅ Registered: {username}")
        return JSONResponse(content={"success": True, "message": "Registration successful!"})
    except Exception as e:
        logger.error(f"❌ Registration error: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Registration failed"})


@app.post("/api/profile/update")
async def update_profile(
        current_user: dict = Depends(get_current_user),
        age: int = Form(None),
        gender: str = Form(None),
        current_password: str = Form(None),
        new_password: str = Form(None)
):
    """Update user profile information"""
    try:
        conn = get_users_db_conn()
        user_id = current_user["id"]

        # Validate inputs
        if age is not None:
            if age < 13 or age > 100:
                conn.close()
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "Age must be between 13-100"}
                )

        if gender is not None:
            if gender not in ["male", "female", "other"]:
                conn.close()
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "Invalid gender"}
                )

        # Handle password change if requested
        if new_password and current_password:
            # Verify current password
            user = conn.execute(
                "SELECT password_hash FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()

            if not verify_password(current_password, user["password_hash"]):
                conn.close()
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "Current password is incorrect"}
                )

            # Validate new password
            if len(new_password) < 6:
                conn.close()
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "New password must be at least 6 characters"}
                )

            # Update with new password
            new_password_hash = hash_password(new_password)
            conn.execute(
                "UPDATE users SET age = COALESCE(?, age), gender = COALESCE(?, gender), password_hash = ? WHERE id = ?",
                (age, gender, new_password_hash, user_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"✅ Profile updated with password change for user {user_id}")
            return JSONResponse(content={"success": True, "message": "Profile and password updated successfully!"})

        # Update without password change
        conn.execute(
            "UPDATE users SET age = COALESCE(?, age), gender = COALESCE(?, gender) WHERE id = ?",
            (age, gender, user_id)
        )
        conn.commit()
        conn.close()
        logger.info(f"✅ Profile updated for user {user_id}")
        return JSONResponse(content={"success": True, "message": "Profile updated successfully!"})

    except Exception as e:
        logger.error(f"❌ Profile update error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Profile update failed"}
        )


@app.post("/api/account/delete")
async def delete_own_account(
        current_user: dict = Depends(get_current_user),
        password: str = Form(...)
):
    """
    Allow user to delete their own account with password confirmation
    This is different from admin deletion - users can only delete their own account
    """
    try:
        conn = get_users_db_conn()
        user_id = current_user["id"]

        # Verify password
        user = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user:
            conn.close()
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "User not found"}
            )

        # Check password
        if not verify_password(password, user["password_hash"]):
            conn.close()
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Incorrect password"}
            )

        # Delete user's data from related tables first
        # Delete chat messages
        conn.execute("""
            DELETE FROM chat_messages 
            WHERE session_id IN (
                SELECT id FROM chat_sessions WHERE user_id = ?
            )
        """, (user_id,))

        # Delete chat sessions
        conn.execute("DELETE FROM chat_sessions WHERE user_id = ?", (user_id,))

        # Delete order items
        conn.execute("""
            DELETE FROM order_items 
            WHERE order_id IN (
                SELECT id FROM orders WHERE user_id = ?
            )
        """, (user_id,))

        # Delete orders
        conn.execute("DELETE FROM orders WHERE user_id = ?", (user_id,))

        # Delete order session
        conn.execute("DELETE FROM order_sessions WHERE user_id = ?", (user_id,))

        # Finally, delete the user
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

        conn.commit()
        conn.close()

        logger.info(f"✅ User {current_user['username']} (ID: {user_id}) deleted their own account")

        return JSONResponse(content={
            "success": True,
            "message": "Account deleted successfully"
        })

    except Exception as e:
        logger.error(f"❌ Account deletion error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Account deletion failed"}
        )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/api/login")
async def login_user(username: str = Form(...), password: str = Form(...)):
    try:
        conn = get_users_db_conn()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not user or not verify_password(password, user["password_hash"]):
            conn.close()
            return JSONResponse(status_code=401, content={"success": False, "message": "Invalid credentials"})
        conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
        conn.commit()
        conn.close()
        token = create_access_token(data={"sub": username})
        response = JSONResponse(content={"success": True, "message": "Login successful",
                                        "user": {"id": user["id"], "username": user["username"],
                                               "age": user["age"], "gender": user["gender"]}})
        response.set_cookie(key="access_token", value=token, httponly=True,
                          max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, samesite="lax")
        logger.info(f"✅ Login: {username}")
        return response
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        return JSONResponse(status_code=500, content={"success": False, "message": "Login failed"})

@app.get("/api/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {"id": current_user["id"], "username": current_user["username"], "age": current_user["age"],
            "gender": current_user["gender"], "created_at": current_user["created_at"],
            "last_login": current_user.get("last_login")}

@app.post("/api/logout")
async def logout():
    response = JSONResponse(content={"success": True, "message": "Logged out"})
    response.delete_cookie("access_token")
    return response

@app.get("/api/current-session")
async def get_session(request: Request, current_user: dict = Depends(get_optional_user)):
    if not current_user:
        return JSONResponse(status_code=401, content={"success": False, "message": "Not authenticated"})
    conn = get_users_db_conn()
    session = conn.execute("SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                          (current_user["id"],)).fetchone()
    if not session:
        cursor = conn.execute("INSERT INTO chat_sessions (user_id, model) VALUES (?, ?)",
                            (current_user["id"], "mistral-large"))
        conn.commit()
        session_id = cursor.lastrowid
    else:
        session_id = session["id"]
    messages = conn.execute("""
                SELECT * FROM (
                    SELECT role, content, timestamp 
                    FROM chat_messages 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 20
                ) AS sub 
                ORDER BY timestamp ASC
                """,
                           (session_id,)).fetchall()

    conn.close()
    return {"session_id": session_id, "messages": [dict(m) for m in messages]}




# Modify the chat_stream function:
# ═══════════════════════════════════════════════════════════════════════════
# CHAT STREAM WITH ORDERING SYSTEM INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/chat-stream")
async def chat_stream(request: Request, current_user: dict = Depends(get_optional_user)):
    data = await request.json()
    message = data.get("message", "")
    history = data.get("history", [])
    model_type = data.get("model_type", "mistral-large")
    session_id = data.get("session_id")

    # Get user ID (None if guest)
    user_id = current_user.get("id") if current_user else None

    # User Profile context
    user_context = ""
    if current_user:
        name = current_user.get("username", "ဧည့်သည်")
        gender = str(current_user.get("gender", "male")).lower()
        title = "ကို" if gender in ["male", "ကျား"] else "မ"
        user_context = f"ဝယ်သူအမည်မှာ {title}{name} ဖြစ်သည်။"

    async def generate():
        try:
            llm = get_llm(model_type)

            # ═══════════════════════════════════════════════════
            # STEP 1: Check Order State
            # ═══════════════════════════════════════════════════
            order_state = get_order_state(user_id, order_db) if user_id else OrderState.BROWSING
            logger.info(f"🛒 Order State: {order_state.value}")

            # ═══════════════════════════════════════════════════
            # STEP 2: Handle Order Flow (if in ordering state)
            # ═══════════════════════════════════════════════════
            if order_state != OrderState.BROWSING and user_id:
                # User is in ordering process
                response = ""
                new_state = order_state

                # Handle different order states
                if order_state == OrderState.CART_CONFIRM:
                    # User is confirming whether to add to cart
                    # This needs to go through handle_buy_intent which checks for "ADD TO CART"
                    session = order_db.load_session(user_id)
                    if session.pending_product:
                        response, new_state = order_manager.handle_buy_intent(
                            user_id, session.pending_product, message
                        )
                    else:
                        # No pending product - reset to browsing
                        response = "ပစ္စည်း ရွေးထားခြင်း မရှိပါ။ ဖုန်း ရွေးပြီး 'I want to buy' လို့ ပြောပါ။"
                        new_state = OrderState.BROWSING
                        session.state = OrderState.BROWSING
                        order_db.save_session(user_id, session)

                elif order_state == OrderState.CART_MANAGEMENT:
                    # User is managing cart (VIEW CART, ADD MORE, CHECKOUT)
                    response, new_state = order_manager.handle_cart_management(user_id, message)

                else:
                    # All other states (checkout flow: address, phone, payment, etc.)
                    response, new_state = order_manager.handle_checkout_flow(user_id, message)

                # Stream the response
                yield f"data: {json.dumps({'text': response})}\n\n"

                # Save to database
                if session_id:
                    try:
                        conn = get_users_db_conn()
                        conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                                     (session_id, "user", message))
                        conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                                     (session_id, "assistant", response))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        logger.error(f"❌ DB error: {e}")

                logger.info(f"✅ Order flow handled: {order_state.value} → {new_state.value}")
                return

            # ═══════════════════════════════════════════════════
            # STEP 3: Get final prompt with understanding
            # ═══════════════════════════════════════════════════
            final_prompt, understanding = logic.get_final_prompt_with_understanding(
                message, history, llm, user_info=user_context
            )

            # ═══════════════════════════════════════════════════
            # STEP 4: Check for Buy Intent
            # ═══════════════════════════════════════════════════
            if understanding.intent == Intent.BUY_PRODUCT:
                # Check authentication first
                if not user_id:
                    # Guest trying to buy - show login message
                    response = """⚠️ Guest အနေနဲ့ Order မတင်နိုင်ပါဘူး။

Order တင်ချင်ရင် အရင် Login လုပ်ပေးပါ။

📌 Login လုပ်ရန် သို့မဟုတ် Register လုပ်ရန် ညာဘက်ထောင့်က Menu ကို နှိပ်ပါ။

Guest အနေဖြင့် ဖုန်းတွေ ကြည့်လို့ရပါတယ်။"""

                    yield f"data: {json.dumps({'text': response})}\n\n"

                    if session_id:
                        try:
                            conn = get_users_db_conn()
                            conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                                       (session_id, "user", message))
                            conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                                       (session_id, "assistant", response))
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            logger.error(f"❌ DB error: {e}")

                    logger.info("✅ Guest buy attempt blocked")
                    return

                # User is authenticated - proceed with buy
                # Extract product info from understanding
                product = None
                full_model = None  # Initialize to avoid undefined variable error

                if understanding.models:
                    # Models contain full name like "iPhone 17 Pro Max"
                    full_model = understanding.models[0]
                    logger.info(f"🔍 Searching for product: {full_model}")

                    # Try to find product by full name first
                    product = order_db.get_product_by_full_name(full_model)

                    # If not found, try splitting brand and model
                    if not product and understanding.brands:
                        brand = understanding.brands[0]
                        # Remove brand from full model to get just the model
                        model = full_model.replace(brand, "").strip()
                        logger.info(f"🔍 Trying split: brand='{brand}', model='{model}'")
                        product = order_db.get_product_by_brand_model(brand, model)

                # If still no product found and we have brands, try aggressive search
                if not product and understanding.brands:
                    brand = understanding.brands[0]
                    logger.info(f"🔍 Aggressive search: looking for any {brand} model in message")
                    # Try to find any product from this brand
                    product = order_db.get_product_by_partial_match(message)

                # Last resort: try searching the entire message for product match
                if not product:
                    logger.info(f"🔍 Last resort: searching entire message for product match")
                    product = order_db.get_product_by_partial_match(message)

                if product:
                    # Handle buy intent through order manager
                    response, new_state = order_manager.handle_buy_intent(
                        user_id, product, message
                    )

                    yield f"data: {json.dumps({'text': response})}\n\n"

                    # Save to database
                    if session_id:
                        try:
                            conn = get_users_db_conn()
                            conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                                       (session_id, "user", message))
                            conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                                       (session_id, "assistant", response))
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            logger.error(f"❌ DB error: {e}")

                    logger.info(f"✅ Buy intent handled: {new_state.value}")
                    return
                else:
                    # Product not found - let LLM handle with normal flow
                    search_term = full_model if full_model else message
                    logger.warning(f"⚠️ Product not found: {search_term} - falling back to LLM")
                    # Continue to normal LLM flow below

            # ═══════════════════════════════════════════════════
            # STEP 5: Handle Cart Commands
            # ═══════════════════════════════════════════════════
            elif understanding.intent == Intent.CART_COMMAND:
                if not user_id:
                    # Guest trying to use cart - show login message
                    response = """⚠️ Guest အနေနဲ့ Cart အသုံးပြု၍ မရပါ။

Order တင်ချင်ရင် အရင် Login လုပ်ပေးပါ။

📌 Login လုပ်ရန် သို့မဟုတ် Register လုပ်ရန် ညာဘက်ထောင့်က Menu ကို နှိပ်ပါ။"""

                    yield f"data: {json.dumps({'text': response})}\n\n"

                    if session_id:
                        try:
                            conn = get_users_db_conn()
                            conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                                       (session_id, "user", message))
                            conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                                       (session_id, "assistant", response))
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            logger.error(f"❌ DB error: {e}")

                    logger.info("✅ Guest cart attempt blocked")
                    return

                # User is authenticated - handle cart command
                response, new_state = order_manager.handle_cart_management(user_id, message)

                yield f"data: {json.dumps({'text': response})}\n\n"

                # Save to database
                if session_id:
                    try:
                        conn = get_users_db_conn()
                        conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                                     (session_id, "user", message))
                        conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                                     (session_id, "assistant", response))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        logger.error(f"❌ DB error: {e}")

                logger.info(f"✅ Cart command handled: {new_state.value}")
                return

            # ═══════════════════════════════════════════════════
            # STEP 6: Normal Product Query (LLM Response)
            # ═══════════════════════════════════════════════════
            messages = [{"role": h.get("role", "user"), "content": h.get("content", "")}
                        for h in history[-4:]]
            messages.append({"role": "user", "content": final_prompt})

            logger.info("🤖 Streaming LLM response...")
            full = ""

            try:
                for chunk in llm.stream(messages):
                    text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    if text:
                        full += text
                        yield f"data: {json.dumps({'text': text})}\n\n"
                        await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"❌ Stream error: {e}")
                resp = llm.invoke(messages)
                full = resp.content if hasattr(resp, 'content') else str(resp)
                yield f"data: {json.dumps({'text': full})}\n\n"

            # ═══════════════════════════════════════════════════
            # STEP 7: Validate Response
            # ═══════════════════════════════════════════════════
            all_products = logic.get_all_products()
            is_valid, validated_response = validate_response(full, understanding, all_products)

            if not is_valid:
                logger.warning("⚠️ Response failed validation, sending fallback")
                correction = validated_response.replace(full, "")
                if correction:
                    yield f"data: {json.dumps({'text': correction, 'corrected': True})}\n\n"
                full = validated_response

            # Save to database
            if current_user and session_id:
                try:
                    conn = get_users_db_conn()
                    conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                                 (session_id, "user", message))
                    conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                                 (session_id, "assistant", full))
                    conn.commit()
                    conn.close()
                    logger.info(f"💾 Saved | Valid: {is_valid}")
                except Exception as e:
                    logger.error(f"❌ DB error: {e}")

            logger.info(f"✅ Done ({len(full)} chars) | Validation: {'PASS' if is_valid else 'FAIL'}")

        except Exception as e:
            logger.error(f"❌ Chat error: {e}")
            yield f"data: {json.dumps({'text': 'စနစ်တွင် ပြဿနာ ရှိနေပါသည်။', 'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/", response_class=HTMLResponse)
@app.get("/chatbot", response_class=HTMLResponse)
async def chatbot(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/inventory", response_class=HTMLResponse)
async def inventory(request: Request, search: str = ""):
    conn = get_db_conn()
    if search:
        items = conn.execute("SELECT * FROM products WHERE brand LIKE ? OR model LIKE ? OR specifications LIKE ? ORDER BY brand, model",
                            (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        items = conn.execute("SELECT * FROM products ORDER BY brand, model").fetchall()
    conn.close()
    return templates.TemplateResponse("inventory.html", {"request": request, "items": items})

@app.get("/manage", response_class=HTMLResponse)
async def manage(request: Request):
    conn = get_db_conn()
    items = conn.execute("SELECT * FROM products ORDER BY brand, model").fetchall()
    conn.close()
    return templates.TemplateResponse("manage.html", {"request": request, "items": items})

@app.get("/add", response_class=HTMLResponse)
async def add_page(request: Request):
    return templates.TemplateResponse("add.html", {"request": request})

@app.post("/add")
async def add(brand: str = Form(...), model: str = Form(...), price: int = Form(...), qty: int = Form(...), specs: str = Form(...), best_for: str = Form(...)):
    conn = get_db_conn()
    conn.execute("INSERT INTO products (brand, model, price, quantity, specifications, best_for) VALUES (?, ?, ?, ?, ?, ?)",
                 (brand, model, price, qty, specs, best_for))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/inventory", status_code=303)

@app.post("/update/{item_id}")
async def update(item_id: int, brand: str = Form(...), model: str = Form(...), price: int = Form(...), qty: int = Form(...), specs: str = Form(...), best_for: str = Form(...), ram_storage: str = Form(...), color: str = Form(...)):
    conn = get_db_conn()
    conn.execute("UPDATE products SET brand=?, model=?, price=?, quantity=?, specifications=?, best_for=?, ram_storage=?, color=? WHERE id=?",
                 (brand, model, price, qty, specs, best_for, ram_storage, color, item_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/manage", status_code=303)

@app.post("/delete/{item_id}")
async def delete(item_id: int):
    conn = get_db_conn()
    conn.execute("DELETE FROM products WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/manage", status_code=303)

# 1. Function to VIEW all users
@app.get("/usersession", response_class=HTMLResponse)
async def view_users(request: Request):
    conn = get_users_db_conn()
    users = conn.execute("SELECT * FROM users ORDER BY username ASC").fetchall()
    conn.close()
    return templates.TemplateResponse("usersession.html", {"request": request, "users": users})

# 2. Function to DELETE a user
@app.post("/users/delete/{user_id}")
async def delete_user(user_id: int):
    conn = get_users_db_conn()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    # Redirect back to the users list after deletion
    return RedirectResponse(url="/usersession", status_code=303)


# User: Get personal order history with items
@app.get("/api/orders")
async def get_user_orders(current_user: dict = Depends(get_current_user)):
    """Get current user's orders with full item details"""
    try:
        with order_db._get_connection() as conn:
            # Get user's orders
            cursor = conn.execute("""
                SELECT 
                    id, order_number, total_amount, delivery_address,
                    phone_number, payment_method, note, transaction_number,
                    status, created_at
                FROM orders
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (current_user["id"],))
            orders = [dict(row) for row in cursor.fetchall()]

            # Get items for each order
            for order in orders:
                cursor = conn.execute("""
                    SELECT 
                        product_id, brand, model, ram_storage, 
                        color, price, quantity
                    FROM order_items
                    WHERE order_id = ?
                """, (order['id'],))
                order['items'] = [dict(row) for row in cursor.fetchall()]

        return {"success": True, "orders": orders}
    except Exception as e:
        logger.error(f"❌ Error fetching user orders: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Failed to fetch orders"}
        )


# Admin: View all orders with full details
@app.get("/api/admin/orders")
async def get_all_orders(current_user: dict = Depends(get_current_user)):
    """Get all orders for admin panel - requires authentication"""
    try:
        with order_db._get_connection() as conn:
            # Get all orders with user information
            cursor = conn.execute("""
                SELECT 
                    o.id, o.order_number, o.user_id, o.total_amount,
                    o.delivery_address, o.phone_number, o.payment_method,
                    o.note, o.transaction_number, o.status, o.created_at,
                    u.username
                FROM orders o
                LEFT JOIN users u ON o.user_id = u.id
                ORDER BY o.created_at DESC
            """)
            orders = [dict(row) for row in cursor.fetchall()]

            # Get order items for each order
            for order in orders:
                cursor = conn.execute("""
                    SELECT 
                        id, product_id, brand, model, ram_storage, 
                        color, price, quantity
                    FROM order_items
                    WHERE order_id = ?
                """, (order['id'],))
                order['items'] = [dict(row) for row in cursor.fetchall()]

        return {"success": True, "orders": orders}
    except Exception as e:
        logger.error(f"❌ Error fetching admin orders: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Failed to fetch orders"}
        )


# Admin: Update order status
@app.post("/api/admin/orders/{order_id}/status")
async def update_order_status(
        order_id: int,
        status: str = Form(...),
        current_user: dict = Depends(get_current_user)
):
    """
    Update order status with inventory management
    - When confirming order: Subtract quantities from inventory
    - When cancelling confirmed order: Restore quantities to inventory
    """
    try:
        valid_statuses = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled']
        if status not in valid_statuses:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Invalid status"}
            )

        # Get current order status and details
        with order_db._get_connection() as conn:
            order = conn.execute(
                "SELECT id, status, order_number FROM orders WHERE id = ?",
                (order_id,)
            ).fetchone()

            if not order:
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "message": "Order not found"}
                )

            old_status = order["status"]
            order_number = order["order_number"]

            # If status is not changing, just return success
            if old_status == status:
                return {"success": True, "message": "Status unchanged"}

            # Get order items
            order_items = conn.execute(
                "SELECT product_id, quantity FROM order_items WHERE order_id = ?",
                (order_id,)
            ).fetchall()

        # ═══════════════════════════════════════════════════════════════
        # INVENTORY MANAGEMENT LOGIC
        # ═══════════════════════════════════════════════════════════════

        # Case 1: Confirming order (pending → confirmed)
        if old_status == 'pending' and status == 'confirmed':
            logger.info(f"📦 Confirming order {order_number} - checking inventory...")

            # Check if sufficient stock available
            with sqlite3.connect(SQLITE_PATH) as products_conn:
                products_conn.row_factory = sqlite3.Row
                insufficient_stock = []

                for item in order_items:
                    product = products_conn.execute(
                        "SELECT id, brand, model, quantity FROM products WHERE id = ?",
                        (item["product_id"],)
                    ).fetchone()

                    if not product:
                        insufficient_stock.append(f"Product ID {item['product_id']} not found")
                    elif product["quantity"] < item["quantity"]:
                        insufficient_stock.append(
                            f"{product['brand']} {product['model']}: "
                            f"Need {item['quantity']}, Only {product['quantity']} available"
                        )

                # If insufficient stock, return error
                if insufficient_stock:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False,
                            "message": "Insufficient stock",
                            "details": insufficient_stock
                        }
                    )

                # Deduct quantities from inventory
                for item in order_items:
                    products_conn.execute(
                        "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                        (item["quantity"], item["product_id"])
                    )
                    logger.info(f"  ✓ Deducted {item['quantity']} units from product ID {item['product_id']}")

                products_conn.commit()

            logger.info(f"✅ Inventory deducted for order {order_number}")

        # Case 2: Cancelling a confirmed/processing/shipped order (restore inventory)
        elif status == 'cancelled' and old_status in ['confirmed', 'processing', 'shipped']:
            logger.info(f"🔄 Cancelling order {order_number} - restoring inventory...")

            # Restore quantities to inventory
            with sqlite3.connect(SQLITE_PATH) as products_conn:
                for item in order_items:
                    products_conn.execute(
                        "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                        (item["quantity"], item["product_id"])
                    )
                    logger.info(f"  ✓ Restored {item['quantity']} units to product ID {item['product_id']}")

                products_conn.commit()

            logger.info(f"✅ Inventory restored for order {order_number}")

        # Update order status
        with order_db._get_connection() as conn:
            conn.execute(
                "UPDATE orders SET status = ? WHERE id = ?",
                (status, order_id)
            )
            conn.commit()

        logger.info(f"✅ Order {order_number} status: {old_status} → {status}")

        return {
            "success": True,
            "message": f"Order status updated to {status}",
            "inventory_updated": status == 'confirmed' or (
                        status == 'cancelled' and old_status in ['confirmed', 'processing', 'shipped'])
        }

    except sqlite3.IntegrityError as e:
        logger.error(f"❌ Database integrity error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Database error"}
        )
    except Exception as e:
        logger.error(f"❌ Error updating order status: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Failed to update status: {str(e)}"}
        )


# Admin: Delete order
@app.post("/api/admin/orders/{order_id}/delete")
async def delete_order(order_id: int, current_user: dict = Depends(get_current_user)):
    """Delete an order - requires authentication"""
    try:
        with order_db._get_connection() as conn:
            # Delete order items first (foreign key constraint)
            conn.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
            # Delete the order
            conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            conn.commit()

        logger.info(f"✅ Order #{order_id} deleted")
        return {"success": True, "message": "Order deleted"}
    except Exception as e:
        logger.error(f"❌ Error deleting order: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Failed to delete order"}
        )


# Admin: Order Management Page
@app.get("/admin/orders", response_class=HTMLResponse)
async def admin_orders_page(request: Request, current_user: dict = Depends(get_current_user)):
    """Admin order management page"""
    return templates.TemplateResponse("admin_orders.html", {
        "request": request,
        "user": current_user
    })


@app.get("/api/admin/orders/{order_id}/stock-check")
async def check_order_stock(order_id: int, current_user: dict = Depends(get_current_user)):
    """Check stock availability for an order"""
    try:
        # Get order items
        with order_db._get_connection() as conn:
            order_items = conn.execute("""
                SELECT oi.product_id, oi.brand, oi.model, oi.quantity as ordered_qty
                FROM order_items oi
                WHERE oi.order_id = ?
            """, (order_id,)).fetchall()

        # Check current stock
        with sqlite3.connect(SQLITE_PATH) as products_conn:
            products_conn.row_factory = sqlite3.Row
            stock_status = []

            for item in order_items:
                product = products_conn.execute(
                    "SELECT quantity FROM products WHERE id = ?",
                    (item["product_id"],)
                ).fetchone()

                current_stock = product["quantity"] if product else 0

                stock_status.append({
                    "product_id": item["product_id"],
                    "brand": item["brand"],
                    "model": item["model"],
                    "ordered_qty": item["ordered_qty"],
                    "current_stock": current_stock,
                    "available": current_stock >= item["ordered_qty"],
                    "status": "ok" if current_stock >= item["ordered_qty"] else ("low" if current_stock > 0 else "out")
                })

        return {"success": True, "items": stock_status}

    except Exception as e:
        logger.error(f"❌ Error checking stock: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)}
        )

@app.exception_handler(HTTPException)
async def http_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"success": False, "message": "Not authenticated"})
        return RedirectResponse(url="/login", status_code=303)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.on_event("startup")
async def startup():
    logger.info("="*80)
    logger.info("🚀 Myanmar Mobile Sales AI - Starting...")
    logger.info(f"📍 Products: {SQLITE_PATH}")
    logger.info(f"📍 Users: {USERS_DB_PATH}")
    logger.info(f"📍 Vector: {CHROMA_PATH}")
    logger.info(f"🤖 Models: {', '.join(MODEL_REGISTRY.keys())}")
    logger.info(f"🔐 SECRET_KEY: {'✅ From .env' if os.getenv('SECRET_KEY') else '⚠️ Default (DEV ONLY)'}")
    logger.info("="*80)

@app.get("/reset")
async def handle_reset(current_user: dict = Depends(get_optional_user)):
    logic.reset_conversation()
    logic.reset_all_metrics()

    # Reset order state if user is logged in
    if current_user:
        reset_order_state(current_user["id"], order_db)
        logger.info(f"🔄 Order state reset for user {current_user['id']}")

    return {"status": "success", "message": "Conversation memory and order state cleared"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)