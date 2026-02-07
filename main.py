import asyncio
import json
import os
import sqlite3
import uvicorn
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from urllib import request

from dotenv import load_dotenv
import hashlib
import jwt
from jwt.exceptions import InvalidTokenError

import logic
from fastapi.responses import StreamingResponse
import pandas as pd
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from starlette.middleware.cors import CORSMiddleware
from logic import get_brand_regex

app = FastAPI()
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY",)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Paths
base_path = os.getenv("BASE_PATH")
SQLITE_PATH = os.path.join(base_path, "phones.db")
CHROMA_PATH = os.path.join(base_path, "chroma_db_v3")
USERS_DB_PATH = os.path.join(base_path, "users.db")

# Shared Embeddings
embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")

# HTTP Bearer for token authentication
security = HTTPBearer()


# === Database Connection Functions ===

def get_db_conn():
    """Get connection to products database"""
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_users_db_conn():
    """Get connection to users database"""
    conn = sqlite3.connect(USERS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_vector_db():
    """Get vector database connection"""
    return Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)


# === Initialize Users Database ===

def init_users_db():
    """Create users table if it doesn't exist"""
    conn = get_users_db_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def init_chat_history_db():
    """Create chat history tables if they don't exist"""
    conn = get_users_db_conn()

    # Chat sessions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            model TEXT DEFAULT 'mistral-large',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    # Chat messages table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


# Initialize databases on startup
init_users_db()
init_chat_history_db()


# === Password Hashing Functions ===

def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return hash_password(plain_password) == hashed_password


# === JWT Token Functions ===

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except InvalidTokenError:
        return None


# === Authentication Dependency ===

async def get_current_user(request: Request):
    """
    Dependency to get current authenticated user from JWT token in cookie.
    Raises HTTPException if not authenticated.
    """
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    # Get user from database
    conn = get_users_db_conn()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return dict(user)


async def get_optional_user(request: Request):
    """
    Optional authentication - returns user if authenticated, None otherwise.
    Does not raise exception.
    """
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


# === Authentication Routes ===

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Serve registration page"""
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/api/register")
async def register_user(
        username: str = Form(...),
        password: str = Form(...),
        age: int = Form(...),
        gender: str = Form(...)
):
    """Register a new user"""
    # Validate input
    if len(username) < 3:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Username must be at least 3 characters"}
        )

    if len(password) < 6:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Password must be at least 6 characters"}
        )

    if age < 13 or age > 100:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Age must be between 13 and 100"}
        )

    if gender not in ["male", "female", "other"]:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Invalid gender"}
        )

    # Check if username already exists
    conn = get_users_db_conn()
    existing_user = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()

    if existing_user:
        conn.close()
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Username already exists"}
        )

    # Create new user
    password_hash = hash_password(password)
    conn.execute(
        "INSERT INTO users (username, password_hash, age, gender) VALUES (?, ?, ?, ?)",
        (username, password_hash, age, gender)
    )
    conn.commit()
    conn.close()

    return JSONResponse(
        content={"success": True, "message": "Account created successfully"}
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve login page"""
    # If already logged in, redirect to home
    user = await get_optional_user(request)
    if user:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/api/login")
async def login_user(
        username: str = Form(...),
        password: str = Form(...)
):
    """Authenticate user and return JWT token"""
    # Get user from database
    conn = get_users_db_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if not user:
        conn.close()
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Invalid username or password"}
        )

    # Verify password
    if not verify_password(password, user["password_hash"]):
        conn.close()
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Invalid username or password"}
        )

    # Update last login
    conn.execute(
        "UPDATE users SET last_login = ? WHERE id = ?",
        (datetime.utcnow(), user["id"])
    )
    conn.commit()
    conn.close()

    # Create access token
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Return success with token in cookie
    response = JSONResponse(
        content={"success": True, "message": "Login successful"}
    )

    # Set HTTP-only cookie with token
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )

    return response


@app.get("/api/logout")
async def logout_user():
    """Logout user by clearing the token cookie"""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="access_token")
    return response


@app.get("/api/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return {
        "username": current_user["username"],
        "age": current_user["age"],
        "gender": current_user["gender"],
        "created_at": current_user["created_at"]
    }


# --- Core Logic Functions (Preserved) ---

def sync_vector(row_dict, delete_first=True):
    vectordb = get_vector_db()
    m_data = {k: (str(v).lower() if isinstance(v, str) else v) for k, v in row_dict.items()}
    page_text = (
        f"Brand: {row_dict.get('brand')} | "
        f"Model: {row_dict.get('model')} | "
        f"Price: {row_dict.get('price')} MMK | "
        f"Stock: {row_dict.get('quantity')} units | "
        f"Specs: {row_dict.get('specifications', '')} | "
        f"BestFor: {row_dict.get('best_for', '')}"
    )

    doc_id = str(row_dict.get('model')).lower()

    if delete_first:
        vectordb.delete(ids=[doc_id])

    vectordb.add_documents(documents=[Document(page_content=page_text, metadata=m_data)], ids=[doc_id])


# --- Protected Routes (Require Authentication) ---

@app.get("/", response_class=HTMLResponse)
async def view_inventory(
        request: Request,
        search: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
):
    """View inventory - requires authentication"""
    conn = get_db_conn()
    query = "SELECT * FROM products"
    params = []
    if search:
        query += " WHERE model LIKE ? OR specifications LIKE ?"
        params = [f"%{search}%", f"%{search}%"]

    items = conn.execute(query, params).fetchall()
    total_products = len(items)
    conn.close()

    # Get dashboard statistics
    users_conn = get_users_db_conn()

    # Total users count
    total_users = users_conn.execute("SELECT COUNT(*) as count FROM users").fetchone()["count"]

    # Active users today
    today = datetime.utcnow().date()
    active_users = users_conn.execute(
        "SELECT COUNT(*) as count FROM users WHERE DATE(last_login) = ?",
        (str(today),)
    ).fetchone()["count"]

    # Total chat sessions
    total_chats = users_conn.execute("SELECT COUNT(*) as count FROM chat_sessions").fetchone()["count"]

    # Total messages
    total_messages = users_conn.execute("SELECT COUNT(*) as count FROM chat_messages").fetchone()["count"]

    users_conn.close()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "items": items,
            "user": current_user,
            "total_products": total_products,
            "active_users": active_users,
            "total_chats": total_chats,
            "total_messages": total_messages
        }
    )


@app.get("/manage", response_class=HTMLResponse)
async def manage_page(
        request: Request,
        current_user: dict = Depends(get_current_user)
):
    """Manage products page - requires authentication"""
    conn = get_db_conn()
    items = conn.execute("SELECT * FROM products").fetchall()
    conn.close()

    return templates.TemplateResponse(
        "manage.html",
        {
            "request": request,
            "items": items,
            "user": current_user
        }
    )


@app.post("/update")
async def update_product(
        model: str = Form(...),
        brand: str = Form(...),
        price: int = Form(...),
        qty: int = Form(...),
        specs: str = Form(...),
        best_for: str = Form(...),
        current_user: dict = Depends(get_current_user)
):
    """Update product - requires authentication"""
    conn = get_db_conn()
    conn.execute(
        "UPDATE products SET brand=?, price=?, quantity=?, specifications=?, best_for=? WHERE model=?",
        (brand, price, qty, specs, best_for, model)
    )
    conn.commit()
    conn.close()

    sync_vector({
        "brand": brand,
        "model": model,
        "price": price,
        "quantity": qty,
        "specifications": specs,
        "best_for": best_for
    })

    get_brand_regex.cache_clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/delete/{model}")
async def delete_product(
        model: str,
        current_user: dict = Depends(get_current_user)
):
    """Delete product - requires authentication"""
    clean_model = model.strip()
    print(f"Attempting to delete: '{clean_model}'")

    conn = get_db_conn()
    cursor = conn.execute(
        "DELETE FROM products WHERE TRIM(LOWER(model)) = LOWER(?)",
        (clean_model,)
    )

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted_count > 0:
        vectordb = get_vector_db()
        vectordb.delete(ids=[clean_model.lower()])
        print(f"Successfully deleted {deleted_count} row(s) from SQL and VectorDB.")
    else:
        print(f"Failed: No product found with model name '{clean_model}'")

    return RedirectResponse(url="/", status_code=303)


@app.get("/add", response_class=HTMLResponse)
async def add_page(
        request: Request,
        current_user: dict = Depends(get_current_user)
):
    """Add product page - requires authentication"""
    return templates.TemplateResponse(
        "add.html",
        {
            "request": request,
            "user": current_user
        }
    )


@app.post("/add")
async def add_product(
        brand: str = Form(...),
        model: str = Form(...),
        price: int = Form(...),
        qty: int = Form(...),
        specs: str = Form(...),
        best_for: str = Form(...),
        current_user: dict = Depends(get_current_user)
):
    """Add product - requires authentication"""
    conn = get_db_conn()
    conn.execute(
        "INSERT INTO products (brand, model, price, quantity, specifications, best_for) VALUES (?,?,?,?,?,?)",
        (brand, model, price, qty, specs, best_for)
    )
    conn.commit()
    conn.close()

    sync_vector(
        {
            "brand": brand,
            "model": model,
            "price": price,
            "quantity": qty,
            "specifications": specs,
            "best_for": best_for
        },
        delete_first=False
    )

    get_brand_regex.cache_clear()
    return RedirectResponse(url="/", status_code=303)


@app.post("/chat-stream")
async def chat_stream(
        req: logic.ChatRequest,
        current_user: dict = Depends(get_current_user)
):
    """Chat stream - requires authentication"""
    selected_llm = logic.models.get(req.model_type, logic.models["mistral-large"])
    prompt_text = logic.get_final_prompt(req.message, req.history, selected_llm)

    # Create or get chat session
    conn = get_users_db_conn()

    # Get or create session for this user
    session = conn.execute(
        "SELECT id FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (current_user["id"],)
    ).fetchone()

    if not session:
        cursor = conn.execute(
            "INSERT INTO chat_sessions (user_id, model) VALUES (?, ?)",
            (current_user["id"], req.model_type)
        )
        session_id = cursor.lastrowid
    else:
        session_id = session["id"]

    # Save user message
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, "user", req.message)
    )
    conn.commit()

    async def event_generator():
        assistant_response = ""
        async for chunk in selected_llm.astream(prompt_text):
            if chunk.content:
                assistant_response += chunk.content
                yield f"data: {json.dumps({'text': chunk.content})}\n\n"

        # Save assistant response after streaming complete
        conn_save = get_users_db_conn()
        conn_save.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, "assistant", assistant_response)
        )
        conn_save.commit()
        conn_save.close()

    conn.close()
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# === User Management Routes ===

@app.get("/user-management", response_class=HTMLResponse)
async def user_management_page(
        request: Request,
        current_user: dict = Depends(get_current_user)
):
    """User management page - requires authentication"""
    conn = get_users_db_conn()

    # Get all users
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()

    # Get statistics
    total_users = len(users)

    # Active users (logged in today)
    today = datetime.utcnow().date()
    active_users = len([u for u in users if u["last_login"] and u["last_login"][:10] == str(today)])

    # New users this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_users_week = len([u for u in users if u["created_at"] and datetime.fromisoformat(u["created_at"]) > week_ago])

    # Gender counts
    male_count = len([u for u in users if u["gender"] == "male"])
    female_count = len([u for u in users if u["gender"] == "female"])

    conn.close()

    return templates.TemplateResponse(
        "user_manage.html",
        {
            "request": request,
            "user": current_user,
            "users": users,
            "total_users": total_users,
            "active_users": active_users,
            "new_users_week": new_users_week,
            "male_count": male_count,
            "female_count": female_count
        }
    )


@app.get("/api/users/{user_id}")
async def get_user(
        user_id: int,
        current_user: dict = Depends(get_current_user)
):
    """Get user details by ID"""
    conn = get_users_db_conn()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return dict(user)


@app.put("/api/users/{user_id}")
async def update_user(
        user_id: int,
        age: int = Form(...),
        gender: str = Form(...),
        current_user: dict = Depends(get_current_user)
):
    """Update user information"""
    conn = get_users_db_conn()

    # Validate
    if age < 13 or age > 100:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Age must be between 13 and 100"}
        )

    if gender not in ["male", "female", "other"]:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Invalid gender"}
        )

    # Update
    conn.execute(
        "UPDATE users SET age = ?, gender = ? WHERE id = ?",
        (age, gender, user_id)
    )
    conn.commit()
    conn.close()

    return JSONResponse(
        content={"success": True, "message": "User updated successfully"}
    )


@app.delete("/api/users/{user_id}")
async def delete_user_by_id(
        user_id: int,
        current_user: dict = Depends(get_current_user)
):
    """Delete user by ID"""
    # Prevent self-deletion
    if user_id == current_user["id"]:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Cannot delete your own account"}
        )

    conn = get_users_db_conn()
    cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted > 0:
        return JSONResponse(
            content={"success": True, "message": "User deleted successfully"}
        )
    else:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "User not found"}
        )


# === Chat History Routes ===

@app.get("/chat-history", response_class=HTMLResponse)
async def chat_history_page(
        request: Request,
        current_user: dict = Depends(get_current_user)
):
    """Chat history page - requires authentication"""
    conn = get_users_db_conn()

    # Get user's chat sessions with message counts
    sessions = conn.execute("""
        SELECT 
            cs.id, 
            cs.model, 
            cs.created_at,
            COUNT(cm.id) as message_count,
            (SELECT content FROM chat_messages WHERE session_id = cs.id ORDER BY timestamp DESC LIMIT 1) as last_message
        FROM chat_sessions cs
        LEFT JOIN chat_messages cm ON cs.id = cm.session_id
        WHERE cs.user_id = ?
        GROUP BY cs.id
        ORDER BY cs.created_at DESC
    """, (current_user["id"],)).fetchall()

    # Get messages for the first session (if any)
    messages = []
    if sessions:
        messages = conn.execute("""
            SELECT * FROM chat_messages 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
        """, (sessions[0]["id"],)).fetchall()

    conn.close()

    return templates.TemplateResponse(
        "chat_history.html",
        {
            "request": request,
            "user": current_user,
            "current_user": current_user,
            "chat_sessions": sessions,
            "messages": messages
        }
    )


@app.get("/api/chat-history/{session_id}")
async def get_chat_session(
        session_id: int,
        current_user: dict = Depends(get_current_user)
):
    """Get chat session messages"""
    conn = get_users_db_conn()

    # Verify session belongs to user
    session = conn.execute(
        "SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?",
        (session_id, current_user["id"])
    ).fetchone()

    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    # Get messages
    messages = conn.execute("""
        SELECT * FROM chat_messages 
        WHERE session_id = ? 
        ORDER BY timestamp ASC
    """, (session_id,)).fetchall()

    conn.close()

    return {
        "session_id": session_id,
        "model": session["model"],
        "created_at": session["created_at"],
        "messages": [dict(m) for m in messages]
    }


@app.get("/api/chat-history/{session_id}/export")
async def export_chat_session(
        session_id: int,
        current_user: dict = Depends(get_current_user)
):
    """Export chat session as JSON"""
    conn = get_users_db_conn()

    # Verify session belongs to user
    session = conn.execute(
        "SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?",
        (session_id, current_user["id"])
    ).fetchone()

    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    # Get messages
    messages = conn.execute("""
        SELECT role, content, timestamp FROM chat_messages 
        WHERE session_id = ? 
        ORDER BY timestamp ASC
    """, (session_id,)).fetchall()

    conn.close()

    export_data = {
        "session_id": session_id,
        "model": session["model"],
        "created_at": session["created_at"],
        "user": current_user["username"],
        "messages": [dict(m) for m in messages]
    }

    from io import BytesIO
    import json

    json_str = json.dumps(export_data, indent=2)
    json_bytes = BytesIO(json_str.encode())

    return StreamingResponse(
        json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=chat_session_{session_id}.json"}
    )


@app.delete("/api/chat-history/{session_id}")
async def delete_chat_session(
        session_id: int,
        current_user: dict = Depends(get_current_user)
):
    """Delete chat session"""
    conn = get_users_db_conn()

    # Verify session belongs to user
    session = conn.execute(
        "SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?",
        (session_id, current_user["id"])
    ).fetchone()

    if not session:
        conn.close()
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Session not found"}
        )

    # Delete session (messages will be deleted via CASCADE)
    conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

    return JSONResponse(
        content={"success": True, "message": "Chat session deleted successfully"}
    )


# === Exception Handlers ===

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions - redirect to login for 401"""
    if exc.status_code == 401:
        # If it's an API call, return JSON
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Not authenticated"}
            )
        # Otherwise redirect to login
        return RedirectResponse(url="/login", status_code=303)

    # For other exceptions, return JSON
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)