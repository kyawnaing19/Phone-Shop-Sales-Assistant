import streamlit as st
import sqlite3
import pandas as pd
import os
import re

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI

# -----------------------------
# Paths & Setup
# -----------------------------
base_path = "/home/pyae-phyo-aung/PycharmProjects/MyanmarMobileSaleChatbot/Mobile_Sales_Project"
sqlite_path = os.path.join(base_path, "phones.db")
chroma_path = os.path.join(base_path, "chroma_db_v3")

# Proxy Setup
PROXY = "socks5://10.58.39.212:1080"
os.environ["http_proxy"] = PROXY
os.environ["https_proxy"] = PROXY
os.environ["ALL_PROXY"] = PROXY

embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")

llm = ChatGoogleGenerativeAI(
    model="gemma-3-27b-it",
    google_api_key="AIzaSyDDMC07yuCcXV9V1XGrbQ2lMOG1iCCedFw",
    temperature=0.2,
)


# -----------------------------
# SQLite Helper (Your original logic)
# -----------------------------
def query_sqlite(query_type, param=None):
    conn = sqlite3.connect(sqlite_path)
    try:
        if query_type == "all_brands":
            res = pd.read_sql("SELECT DISTINCT brand FROM products", conn)
            return "ဆိုင်တွင် ရရှိနိုင်သော Brand များမှာ: " + ", ".join(res['brand'].astype(str).tolist())
        elif query_type == "price_filter":
            res = pd.read_sql(f"SELECT brand, model, price FROM products WHERE price <= {param} LIMIT 15", conn)
            if res.empty:
                return "ထိုဈေးနှုန်းအောက် ဖုန်းမရှိသေးပါခင်ဗျာ။"
            return "ရရှိနိုင်သော ဖုန်းများ:\n" + res.to_string(index=False)
    finally:
        conn.close()


# -----------------------------
# Load Vector DB
# -----------------------------
@st.cache_resource
def load_vector_db():
    return Chroma(persist_directory=chroma_path, embedding_function=embeddings)


vector_db = load_vector_db()


# -----------------------------
# History Processor (New Step for Real-world Practice)
# -----------------------------
def get_standalone_query(message, history):
    if not history:
        return message

    # History ကို စာသားအဖြစ်ပြောင်းခြင်း (နောက်ဆုံး ၅ ခု)
    history_str = ""
    for msg in history[-5:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n"

    # ဤနေရာတွင် LLM ကို သုံးပြီး မေးခွန်းကို standalone ပြောင်းခိုင်းခြင်း
    rewrite_prompt = f"""
    Chat History နှင့် User ၏ မေးခွန်းကို ကြည့်၍ Standalone Question တစ်ခု ပြန်ရေးပါ။

    လိုက်နာရန် စည်းကမ်းများ:
    - User က Model အသစ် (သို့မဟုတ်) Brand အသစ်ကို တိုက်ရိုက်အမည်တပ်၍ မေးလာပါက History ကို လုံးဝ (လုံးဝ) ထည့်မစဉ်းစားပါနှင့်။ အဆိုပါ Model အသစ်ကိုသာ ရှာဖွေခိုင်းပါ။
    - ဝယ်သူ မေးနေသော "အကြောင်းအရာ (Subject)" နှင့် "တိကျသော Model နာမည်" ကို သေချာ ခွဲခြားပါ။
    - ဥပမာ: "Pro" ဟု ပါလျှင် "Pro" ကိုသာ ထည့်ပါ။ "Pro Max" သို့မဟုတ် Standard model များနှင့် လုံးဝ မရောထွေးပါစေနှင့်။
    - အကယ်၍ ဝယ်သူက "သူ့ရဲ့" သို့မဟုတ် "အဲဒါ" ဟု သုံးနှုန်းလျှင် History ထဲရှိ နောက်ဆုံးပြောခဲ့သော တိကျသည့် Model နာမည်ဖြင့် အစားထိုးပါ။
    - မေးခွန်းထဲတွင် မပါသော Model များ၊ Brands များကို လုံးဝ (လုံးဝ) ထပ်မဖြည့်ပါနှင့်။
    - မေးခွန်းအသစ်က ယခင်မေးခွန်းနှင့် မသက်ဆိုင်ပါက မေးခွန်းအသစ်အတိုင်းသာ သီးသန့်ရေးပါ။

    Chat History: {history_str}
    User Question: {message}
    Standalone Question:"""

    response = llm.invoke(rewrite_prompt)
    return response.content


# ... (အပေါ်က Import နဲ့ Setup အပိုင်းတွေ အတူတူပဲဖြစ်ရပါမယ်) ...

# -----------------------------
# Metadata Helper (New)
# -----------------------------
def extract_brand(text):
    """စာသားထဲမှ Brand နာမည်ကို ခွဲထုတ်ရန် (Simple logic သို့မဟုတ် LLM သုံးနိုင်သည်)"""
    brands = ["apple", "samsung", "vivo", "oppo", "xiaomi", "tecno", "redmi", "realme", "huawei"]
    text_lower = text.lower()
    for b in brands:
        if b in text_lower:
            return b
    return None


# -----------------------------
# Dialog Manager (Updated with Metadata Filter)
# -----------------------------
def dialog_manager_assistant(message, history):
    # အဆင့် ၁ - History ကို အခြေခံပြီး Standalone Query ပြောင်းခြင်း
    search_query = get_standalone_query(message, history)
    msg_lower = search_query.lower()
    context = ""

    # အဆင့် ၂ - SQL logic (Brand list သို့မဟုတ် Price Filter)
    if any(x in msg_lower for x in ["brand", "ဘာတံဆိပ်", "ဘာ brand"]):
        context = query_sqlite("all_brands")
    elif "အောက်" in msg_lower and ("သိန်း" in msg_lower or "ကျပ်" in msg_lower):
        nums = re.findall(r'\d+', search_query)
        if nums:
            limit = int(nums[0]) * 1000000 if "သိန်း" in search_query else int(nums[0])
            context = query_sqlite("price_filter", limit)

    # အဆင့် ၃ - Vector Search (Metadata Filter ဖြင့် အဆင့်မြှင့်တင်ခြင်း)
    if not context:
        # မေးခွန်းထဲကနေ Brand ကို ခွဲထုတ်မယ်
        target_brand = extract_brand(search_query)

        # Filter သတ်မှတ်ခြင်း (Admin Panel က lower() နဲ့ သိမ်းခဲ့တာကို သတိပြုပါ)
        metadata_filter = {"brand": target_brand} if target_brand else None

        # Search လုပ်တဲ့နေရာမှာ filter ထည့်လိုက်ခြင်းဖြင့် မဆိုင်တဲ့ Brand တွေ ပါမလာတော့ပါ
        docs = vector_db.similarity_search(
            search_query,
            k=5,  # k ကို ၁၀ ကနေ ၅ ကို လျှော့ခြင်းဖြင့် ပိုမိုတိကျစေသည်
            filter=metadata_filter
        )
        context = "\n".join([d.page_content for d in docs])

    # အဆင့် ၄ - Final Answer (သင့်ရဲ့ မူရင်း Prompt)
    prompt = f"""
သင်သည် ယဉ်ကျေးပျူငှာသော မြန်မာဖုန်းအရောင်းဝန်ထမ်း ဖြစ်သည်။
အောက်ပါ Context ကိုသာ အခြေခံ၍ ဝယ်သူကို လိုရင်းသာ ဖြေကြားပေးပါ။
စာကြောင်းများကို ထပ်ခါတလဲလဲ မပြောပါနှင့်။ မြန်မာဘာသာစကားသာသုံးပါ ။ စာလုံးပေါင်းသတ်ပုံမှန်ကန်အောင်သုံးပါ။

လိုက်နာရမည့်စည်းကမ်းများ:
- Context ထဲမှာ မပါရင် မခန့်မှန်းပါနဲ့။
- User မေးထားသော သီးသန့် Model ({search_query}) နှင့်သာ ဆိုင်သော အချက်အလက်ကို ဦးစားပေး ဖြေကြားပါ။
- မဆိုင်သော Model များကို ထည့်မပြောပါနှင့်။
- မသေချာရင် "မရှိပါ/မသေချာပါ" လို့ပြောပါ
- ဖုန်း brand name ကိုပြည့်စုံစွာပြောပါ
- user မေးခွန်းမှာပါဝင်တဲ့ specifications နဲ့ကိုက်ညီတဲ့ ဖုန်းအားလုံးပြပါ
- အချက်အလက် နည်းပါက တိုက်ရိုက်ယဉ်ကျေးစွာ ဖြေကြားပါ

Context: {context}

User Question: {message}

မြန်မာလို ယဉ်ကျေးစွာ ဖြေကြားပေးပါ။
"""
    return llm.invoke(prompt).content


# ... (ကျန်တဲ့ Streamlit UI အပိုင်းတွေ အတူတူပါပဲ) ...


# -----------------------------
# Streamlit UI (Your original UI)
# -----------------------------
st.set_page_config(page_title="Mobile Sales AI", page_icon="🇲🇲")
st.title("🇲🇲 Smart Mobile Sales AI")

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    if st.button("🔄 Reload Vector DB"):
        st.cache_resource.clear()
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt_input := st.chat_input("ဖုန်းအကြောင်း မေးမြန်းနိုင်ပါသည်..."):
    st.session_state.messages.append({"role": "user", "content": prompt_input})
    with st.chat_message("user"):
        st.markdown(prompt_input)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        try:
            # st.session_state.messages ကို history အဖြစ် ထည့်ပေးလိုက်ခြင်း
            assistant_response = dialog_manager_assistant(prompt_input, st.session_state.messages[:-1])
            full_response = assistant_response
        except Exception as e:
            full_response = f"⚠️ Error: {str(e)}"
            st.error(full_response)

        message_placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})