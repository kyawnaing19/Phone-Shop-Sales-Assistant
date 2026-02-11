"""Myanmar Mobile Sales AI Assistant - Fixed Version"""
import asyncio, json, os, sqlite3, uvicorn, hashlib, jwt, logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from dotenv import load_dotenv
from jwt.exceptions import InvalidTokenError
import logic
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_nvidia_ai_endpoints import ChatNVIDIA

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


@app.post("/chat-stream")
async def chat_stream(request: Request, current_user: dict = Depends(get_optional_user)):
    data = await request.json()
    message = data.get("message", "")
    history = data.get("history", [])
    model_type = data.get("model_type", "mistral-large")
    session_id = data.get("session_id")

    # 1. User Profile context တည်ဆောက်ခြင်း
    user_context = ""
    if current_user:
        name = current_user.get("username", "ဧည့်သည်")
        gender = str(current_user.get("gender", "male")).lower()

        # နာမ်စား ခွဲခြားခြင်း
        title = "ကို" if gender in ["male", "ကျား"] else "မ"
        # စာသားအနေနဲ့ AI ကို ညွှန်ကြားချက်ပေးခြင်း
        user_context = f"ဝယ်သူအမည်မှာ {title}{name} ဖြစ်သည်။"

    async def generate():
        try:
            llm = get_llm(model_type)
            # 2. logic function ဆီသို့ user_context လှမ်းပို့ခြင်း
            final_prompt = logic.get_final_prompt(message, history, llm, user_info=user_context)
            messages = [{"role": h.get("role", "user"), "content": h.get("content", "")} for h in history[-4:]]
            messages.append({"role": "user", "content": final_prompt})
            logger.info("🤖 Streaming...")
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
            if current_user and session_id:
                try:
                    conn = get_users_db_conn()
                    conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                               (session_id, "user", message))
                    conn.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                               (session_id, "assistant", full))
                    conn.commit()
                    conn.close()
                    logger.info(f"💾 Saved")
                except Exception as e:
                    logger.error(f"❌ DB error: {e}")
            logger.info(f"✅ Done ({len(full)} chars)")
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
async def update(item_id: int, brand: str = Form(...), model: str = Form(...), price: int = Form(...), qty: int = Form(...), specs: str = Form(...), best_for: str = Form(...)):
    conn = get_db_conn()
    conn.execute("UPDATE products SET brand=?, model=?, price=?, quantity=?, specifications=?, best_for=? WHERE id=?",
                 (brand, model, price, qty, specs, best_for, item_id))
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)