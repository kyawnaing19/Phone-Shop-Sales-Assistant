import streamlit as st
import sqlite3
import pandas as pd
import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# -----------------------------
# Paths & Setup
# -----------------------------
base_path = r"C:\Users\MCC-DeLL\PycharmProjects\PhoneshopSaleAssitant\Mobile_Sales_Project"
sqlite_path = os.path.join(base_path, "phones.db")
chroma_path = os.path.join(base_path, "chroma_db_v3")

embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")


def get_connection():
    return sqlite3.connect(sqlite_path)


# -----------------------------
# Optimized Incremental Vector DB Logic
# -----------------------------
def get_vector_db():
    return Chroma(persist_directory=chroma_path, embedding_function=embeddings)


def add_or_update_vector(row_dict):
    """တစ်ခုချင်းစီအလိုက် Vector DB တွင် အသစ်ထည့်ခြင်း သို့မဟုတ် ပြင်ဆင်ခြင်း"""
    try:
        vectordb = get_vector_db()

        # Metadata သန့်စင်ခြင်း (Search ပိုကောင်းစေရန် Lowercase ပြောင်းသည်)
        m_data = {k: (str(v).lower() if isinstance(v, str) else v) for k, v in row_dict.items()}

        page_text = (
            f"Brand: {row_dict.get('brand', '')} | "
            f"Model: {row_dict.get('model', '')} | "
            f"Price: {row_dict.get('price', '')} MMK | "
            f"Specs: {row_dict.get('specifications', '')} | "
            f"BestFor: {row_dict.get('best_for', '')}"
        )

        doc_id = str(row_dict.get('model', '')).lower()

        # ရှိပြီးသား ID ဖြစ်ပါက အရင်ဖျက်ပြီးမှ အသစ်ပြန်ထည့်ခြင်း (Update Logic)
        vectordb.delete(ids=[doc_id])

        vectordb.add_documents(
            documents=[Document(page_content=page_text, metadata=m_data)],
            ids=[doc_id]
        )
        return True
    except Exception as e:
        st.error(f"❌ Sync Error: {e}")
        return False


def delete_from_vector(model_name):
    """Vector DB ထဲမှ သတ်မှတ်ထားသော Model ကို ဖျက်ထုတ်ခြင်း"""
    try:
        vectordb = get_vector_db()
        vectordb.delete(ids=[str(model_name).lower()])
        return True
    except Exception as e:
        st.error(f"❌ Delete Sync Error: {e}")
        return False


def full_sync_rebuild():
    """လိုအပ်ပါက တစ်ခုလုံးကို အစမှ ပြန်လည် Sync လုပ်ရန် (Initial Setup အတွက်)"""
    try:
        conn = get_connection()
        df = pd.read_sql("SELECT * FROM products", conn)
        conn.close()

        if df.empty:
            st.warning("⚠️ No data in SQLite.")
            return False

        # အကုန်လုံးကို တစ်လုံးချင်းစီ add_or_update လုပ်ပေးသွားမည်
        for _, row in df.iterrows():
            add_or_update_vector(row.to_dict())
        return True
    except Exception as e:
        st.error(f"❌ Full Sync Error: {e}")
        return False


# -----------------------------
# UI Setup
# -----------------------------
st.set_page_config(page_title="Mobile Admin Pro", layout="wide")
st.title("📱 Mobile Store Management System (Incremental Sync)")

with st.sidebar:
    st.header("Admin Tools")
    if st.button("🔄 Full Re-Sync (Slow)", use_container_width=True):
        if full_sync_rebuild():
            st.success("✅ Full Vector DB rebuilt!")
            st.rerun()

tab1, tab2, tab3 = st.tabs(["🔍 View Inventory", "📝 Edit & Delete", "➕ Add New Product"])

# -----------------------------
# SECTION 1: VIEW
# -----------------------------
with tab1:
    st.header("Inventory Overview")
    conn = get_connection()
    df_view = pd.read_sql("SELECT * FROM products", conn)
    conn.close()

    if df_view.empty:
        st.warning("No products found.")
    else:
        col1, col2, col3 = st.columns(3)
        f_brand = col1.multiselect("Filter by Brand", options=sorted(df_view['brand'].unique().tolist()))
        f_min_price, f_max_price = col2.slider("Price Range", int(df_view['price'].min()), int(df_view['price'].max()),
                                               (int(df_view['price'].min()), int(df_view['price'].max())))
        f_search = col3.text_input("Search Model or Specs")

        if f_brand: df_view = df_view[df_view['brand'].isin(f_brand)]
        df_view = df_view[(df_view['price'] >= f_min_price) & (df_view['price'] <= f_max_price)]
        if f_search:
            df_view = df_view[
                df_view['model'].astype(str).str.contains(f_search, case=False) | df_view['specifications'].astype(
                    str).str.contains(f_search, case=False)]

        st.dataframe(df_view, use_container_width=True, height=400)

# -----------------------------
# SECTION 2: EDIT & DELETE
# -----------------------------
with tab2:
    st.header("Manage Existing Products")
    if df_view.empty:
        st.warning("No products selected.")
    else:
        selected_model = st.selectbox("Select Model to Action", df_view['model'].astype(str).tolist())
        if selected_model:
            conn = get_connection()
            item = pd.read_sql("SELECT * FROM products WHERE model=?", conn, params=(selected_model,)).iloc[0]
            conn.close()

            with st.expander(f"Editing: {selected_model}", expanded=True):
                e_brand = st.text_input("Brand", value=str(item['brand']))
                e_price = st.number_input("Price", value=int(item['price']), min_value=0)
                e_specs = st.text_area("Specifications", value=str(item['specifications']))
                e_best = st.text_area("Best For", value=str(item['best_for']))

                c1, c2 = st.columns(2)
                if c1.button("💾 Update Changes", use_container_width=True):
                    conn = get_connection()
                    conn.execute("UPDATE products SET brand=?, price=?, specifications=?, best_for=? WHERE model=?",
                                 (e_brand, int(e_price), e_specs, e_best, selected_model))
                    conn.commit()
                    conn.close()

                    # Incremental Update
                    add_or_update_vector(
                        {"brand": e_brand, "model": selected_model, "price": e_price, "specifications": e_specs,
                         "best_for": e_best})
                    st.success("✅ SQLite Updated + Vector Synced!")
                    st.rerun()

                if c2.button("🗑️ Delete Product", use_container_width=True, type="primary"):
                    conn = get_connection()
                    conn.execute("DELETE FROM products WHERE model=?", (selected_model,))
                    conn.commit()
                    conn.close()

                    # Incremental Delete
                    delete_from_vector(selected_model)
                    st.warning("🗑️ Deleted from System!")
                    st.rerun()

# -----------------------------
# SECTION 3: ADD
# -----------------------------
with tab3:
    st.header("Add New Entry")
    with st.form("add_form", clear_on_submit=True):
        a_brand = st.text_input("Brand Name")
        a_model = st.text_input("Model Name")
        a_price = st.number_input("Price (MMK)", min_value=0)
        a_specs = st.text_area("Specifications")
        a_best = st.text_area("Best For")
        submitted = st.form_submit_button("➕ Add Product to System")

        if submitted and a_brand and a_model:
            conn = get_connection()
            conn.execute("INSERT INTO products (brand, model, price, specifications, best_for) VALUES (?,?,?,?,?)",
                         (a_brand, a_model, int(a_price), a_specs, a_best))
            conn.commit()
            conn.close()

            # Incremental Add
            add_or_update_vector(
                {"brand": a_brand, "model": a_model, "price": a_price, "specifications": a_specs, "best_for": a_best})
            st.success("✅ New product added and synced!")