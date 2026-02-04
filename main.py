import asyncio
import json
import os
import sqlite3
import logic
from fastapi.responses import StreamingResponse
import pandas as pd
from typing import Optional
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

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

# Paths
base_path = os.getenv("BASE_PATH")
SQLITE_PATH = os.path.join(base_path, "phones.db")
CHROMA_PATH = os.path.join(base_path, "chroma_db_v3")

# Shared Embeddings
embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")


def get_db_conn():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_vector_db():
    return Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)


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
    )  # <--- ဒီလက်သည်းကွင်းကို ဒီနေရာရောက်မှ ပိတ်ရပါမယ်

    doc_id = str(row_dict.get('model')).lower()

    if delete_first:
        vectordb.delete(ids=[doc_id])

    vectordb.add_documents(documents=[Document(page_content=page_text, metadata=m_data)], ids=[doc_id])


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def view_inventory(request: Request, search: Optional[str] = None):
    conn = get_db_conn()
    query = "SELECT * FROM products"
    params = []
    if search:
        query += " WHERE model LIKE ? OR specifications LIKE ?"
        params = [f"%{search}%", f"%{search}%"]

    items = conn.execute(query, params).fetchall()
    conn.close()
    return templates.TemplateResponse("inventory.html", {"request": request, "items": items})


@app.get("/manage", response_class=HTMLResponse)
async def manage_page(request: Request):
    conn = get_db_conn()
    items = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return templates.TemplateResponse("manage.html", {"request": request, "items": items})


@app.post("/update")
async def update_product(model: str = Form(...), brand: str = Form(...), price: int = Form(...), qty: int = Form(...), specs: str = Form(...),
                         best_for: str = Form(...)):
    conn = get_db_conn()
    conn.execute("UPDATE products SET brand=?, price=?, quantity=?, specifications=?, best_for=? WHERE model=?",
                 (brand, price,qty, specs, best_for, model))
    conn.commit()
    conn.close()




    sync_vector({"brand": brand, "model": model, "price": price, "quantity": qty, "specifications": specs, "best_for": best_for})
    # logic.py ကနေ import လုပ်ထားတဲ့ function ရဲ့ cache ကို ရှင်းမယ်
    get_brand_regex.cache_clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/delete/{model}")
async def delete_product(model: str):
    # URL ကလာတဲ့ %20 တွေကို Space အဖြစ် သေချာပြောင်းပြီး ရှေ့နောက် space ဖြတ်မယ်
    clean_model = model.strip()
    print(f"Attempting to delete: '{clean_model}'")

    conn = get_db_conn()
    # TRIM(model) က database ထဲက space တွေကို ဖြတ်ပေးပြီး
    # LOWER က စာလုံးအကြီးအသေး ညှိပေးပါတယ်
    cursor = conn.execute(
        "DELETE FROM products WHERE TRIM(LOWER(model)) = LOWER(?)",
        (clean_model,)
    )

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted_count > 0:
        # Vector DB ကနေလည်း ဖျက်မယ်
        vectordb = get_vector_db()
        vectordb.delete(ids=[clean_model.lower()])
        print(f"Successfully deleted {deleted_count} row(s) from SQL and VectorDB.")
    else:
        print(f"Failed: No product found with model name '{clean_model}'")

    return RedirectResponse(url="/", status_code=303)



@app.get("/add", response_class=HTMLResponse)
async def add_page(request: Request):
    return templates.TemplateResponse("add.html", {"request": request})


@app.post("/add")
async def add_product(brand: str = Form(...), model: str = Form(...), price: int = Form(...), qty: int = Form(...), specs: str = Form(...),
                      best_for: str = Form(...)):
    conn = get_db_conn()
    conn.execute("INSERT INTO products (brand, model, price, quantity, specifications, best_for) VALUES (?,?,?,?,?,?)",
                 (brand, model, price, qty, specs, best_for))
    conn.commit()
    conn.close()



    sync_vector({"brand": brand, "model": model, "price": price, "quantity": qty, "specifications": specs, "best_for": best_for},
                delete_first=False)
    # logic.py ကနေ import လုပ်ထားတဲ့ function ရဲ့ cache ကို ရှင်းမယ်
    get_brand_regex.cache_clear()
    return RedirectResponse(url="/", status_code=303)


@app.post("/chat-stream")
async def chat_stream(req: logic.ChatRequest):
    # logic ထဲက standalone query နဲ့ final prompt ကို တွက်ချက်ခြင်း
    prompt_text = logic.get_final_prompt(req.message, req.history)

    async def event_generator():
        # LLM streaming
        for chunk in logic.llm.stream(prompt_text):
            if chunk.content:
                yield f"data: {json.dumps({'text': chunk.content})}\n\n"
            await asyncio.sleep(0.01)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Sync Utility Route ---
# @app.get("/sync-all-v2")
# async def sync_all_v2(key: str = None):
#     if key != "mysecret123":  # ဒီနေရာမှာ secret key တစ်ခုသတ်မှတ်ထားပါ
#         return {"error": "Unauthorized"}
#
#     conn = get_db_conn()
#     items = conn.execute("SELECT * FROM products").fetchall()
#     conn.close()
#     for item in items:
#         sync_vector(dict(item))
#     return {"status": "Sync Complete"}