import sqlite3
from functools import lru_cache
import pandas as pd
import os
import re

from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel


# Proxy & Paths
# PROXY = "socks5://10.58.39.212:1080"
# os.environ["http_proxy"] = PROXY
# os.environ["https_proxy"] = PROXY
# os.environ["ALL_PROXY"] = PROXY

# ရှေ့မှာ r ထည့်လိုက်ပါ
base_path = r"C:\Users\MCC-DeLL\PycharmProjects\PhoneshopSaleAssitant\Mobile_Sales_Project"
sqlite_path = os.path.join(base_path, "phones.db")
chroma_path = os.path.join(base_path, "chroma_db_v3")

embeddings = HuggingFaceEmbeddings(
    model_name="paraphrase-multilingual-MiniLM-L12-v2"
)

load_dotenv()

# API Key ကို OS environment ထဲကနေ ဆွဲထုတ်ပါမယ်
google_api_key = os.getenv("GOOGLE_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemma-3-27b-it",
    google_api_key=google_api_key,
    temperature=0.2,
)

vector_db = Chroma(
    persist_directory=chroma_path,
    embedding_function=embeddings
)


def get_all_brands_from_db():
    conn = sqlite3.connect(sqlite_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT brand FROM products")

        return [
            row[0].lower()
            for row in cursor.fetchall()
            if row[0]
        ]

    except Exception as e:
        print(f"Error fetching brands: {e}")
        return []

    finally:
        conn.close()


class ChatRequest(BaseModel):
    message: str
    history: list = []

def format_kyat_mm(price):
    lakh = price // 100000
    rem = price % 100000

    thou10 = rem // 10000
    rem = rem % 10000

    thou1 = rem // 1000

    parts = []

    if lakh:
        parts.append(f"{lakh} သိန်း")
    if thou10:
        parts.append(f"{thou10} သောင်း")
    if thou1:
        parts.append(f"{thou1} ထောင်")

    return " ".join(parts) + " ကျပ်"

def query_sqlite(query_type, param=None):

    conn = sqlite3.connect(sqlite_path)

    try:

        # ===== ALL BRANDS =====
        if query_type == "all_brands":
            res = pd.read_sql(
                """
                SELECT DISTINCT TRIM(brand) as brand
                FROM products
                ORDER BY brand
                """,
                conn,
            )

            return "ဆိုင်တွင် ရရှိနိုင်သော Brand များမှာ: " + ", ".join(
                res["brand"].tolist()
            )

        # ===== BRAND FILTER =====
        elif query_type == "brand_filter":

            res = pd.read_sql(
                """
                SELECT DISTINCT model, price
                FROM products
                WHERE LOWER(TRIM(brand)) = LOWER(TRIM(?))
                ORDER BY price DESC
                """,
                conn,
                params=[param],
            )

            if not res.empty:
                res["price"] = res["price"].apply(format_kyat_mm)
                return f"{param.capitalize()} Brand မှာ ရရှိနိုင်သော Model များ:\n" + res.to_string(index=False)

            return f"{param.capitalize()} Brand မော်ဒယ်များ လက်ရှိတွင် မရှိသေးပါ။"

        # ===== PRICE FILTER MAX (အောက်) =====
        elif query_type == "price_filter_max":

            if isinstance(param, tuple):
                brand, price_val = param

                res = pd.read_sql(
                    """
                    SELECT brand, model, price
                    FROM products
                    WHERE LOWER(TRIM(brand)) = LOWER(TRIM(?))
                    AND price <= ?
                    ORDER BY price DESC
                    LIMIT 20
                    """,
                    conn,
                    params=[brand, price_val],
                )

                msg_empty = (
                    f"{brand.capitalize()} Brand အတွက် {format_kyat_mm(price_val)} အောက် ဖုန်းမရှိသေးပါ။"
                )

                if res.empty:
                    return msg_empty

                res["price"] = res["price"].apply(format_kyat_mm)

                return (
                    f"{brand.capitalize()} Brand မှာ {format_kyat_mm(price_val)} အောက် ဖုန်းများ:\n"
                    + res.to_string(index=False)
                )

            else:
                price_val = param

                res = pd.read_sql(
                    """
                    SELECT brand, model, price
                    FROM products
                    WHERE price <= ?
                    ORDER BY price DESC
                    LIMIT 20
                    """,
                    conn,
                    params=[price_val],
                )

                msg_empty = f"{format_kyat_mm(price_val)} အောက် ဖုန်းမရှိသေးပါ။"

                if res.empty:
                    return msg_empty

                res["price"] = res["price"].apply(format_kyat_mm)

                return "ရရှိနိုင်သော ဖုန်းများ:\n" + res.to_string(index=False)

        # ===== PRICE FILTER MIN (အထက်) =====
        elif query_type == "price_filter_min":

            if isinstance(param, tuple):
                brand, price_val = param

                res = pd.read_sql(
                    """
                    SELECT brand, model, price
                    FROM products
                    WHERE LOWER(TRIM(brand)) = LOWER(TRIM(?))
                    AND price >= ?
                    ORDER BY price DESC
                    LIMIT 20
                    """,
                    conn,
                    params=[brand, price_val],
                )

                msg_empty = (
                    f"{brand.capitalize()} Brand အတွက် {format_kyat_mm(price_val)} အထက် ဖုန်းမရှိသေးပါ။"
                )

                if res.empty:
                    return msg_empty

                res["price"] = res["price"].apply(format_kyat_mm)

                return (
                    f"{brand.capitalize()} Brand မှာ {format_kyat_mm(price_val)} အထက် ဖုန်းများ:\n"
                    + res.to_string(index=False)
                )

            else:
                price_val = param

                res = pd.read_sql(
                    """
                    SELECT brand, model, price
                    FROM products
                    WHERE price >= ?
                    ORDER BY price DESC
                    LIMIT 20
                    """,
                    conn,
                    params=[price_val],
                )

                msg_empty = f"{format_kyat_mm(price_val)} အထက် ဖုန်းမရှိသေးပါ။"

                if res.empty:
                    return msg_empty

                res["price"] = res["price"].apply(format_kyat_mm)

                return "ရရှိနိုင်သော ဖုန်းများ:\n" + res.to_string(index=False)

    finally:
        conn.close()


# ၂။ Regex Pattern ကို Cache လုပ်ထားခြင်း
@lru_cache(maxsize=1)
def get_brand_regex():

    brands = get_all_brands_from_db()

    if not brands:
        return None

    pattern_str = r"\b(" + "|".join(map(re.escape, brands)) + r")\b"
    return re.compile(pattern_str, re.IGNORECASE)


def extract_brands(text):
    if not text:
        return []

    pattern = get_brand_regex()

    if pattern:
        matches = pattern.findall(text)
        return list(set([m.lower() for m in matches]))

    return []



def get_final_prompt(message, history):

    # 1. Standalone Query Rewrite
    history_str = ""

    if history:
        for msg in history[-5:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_str += f"{role}: {msg['content']}\n"

    rewrite_prompt = f"""
Chat History နှင့် User ၏ မေးခွန်းကို ကြည့်၍ Standalone Question တစ်ခု ပြန်ရေးပါ။
Thai, Korea, India, Chinese, Japanese and other ဘာသာစကားတွေ မသုံးပါနဲ့။

လိုက်နာရန် စည်းကမ်းများ:
- Only use history if user didn’t specify exact model or brand.
- If model/brand exists in current message, use it as-is.
- If the user asks about a new model or a new brand directly, do not include any history. Only search for the newly mentioned model.
- Clearly distinguish between the subject the user is asking about and the exact model name.
- For example, if the user mentions "Pro", only include "Pro". Do not mix it with "Pro Max" or standard models.
- If the user uses pronouns like "their" or "that", replace them with the exact model name from the most recent relevant history.
- Do not add any models or brands that are not mentioned in the user’s question.
- If the new question is unrelated to previous questions, treat it as a completely independent question.

Chat History:
{history_str}

User Question:
{message}

Standalone Question:
"""

    search_query = llm.invoke(rewrite_prompt).content

    msg_lower = message.lower()
    context = ""

    # target_brands = extract_brands(search_query) or extract_brands(message)
    target_brands = extract_brands(message)

    print("search_query:", search_query)
    print("message:", message)
    print("brands extracted:", target_brands)
    print("history:", history_str)

    # Brand + Price FIRST
    contexts = []

    if target_brands and ("အထက်" in msg_lower or "အောက်" in msg_lower):

        print("enter Pricefilter with multi brand")
        nums = re.findall(r'\d+', message)

        if nums:
            price_value = int(nums[0]) * 100000 if "သိန်း" in message else int(nums[0])

            for brand in target_brands:
                if "အောက်" in msg_lower:
                    contexts.append(
                        query_sqlite("price_filter_max", (brand, price_value))
                    )
                else:
                    contexts.append(
                        query_sqlite("price_filter_min", (brand, price_value))
                    )

            context = "\n\n".join(contexts)


    # Brand + Model
    elif target_brands and (
            "model" in msg_lower
            or "မော်ဒယ်" in msg_lower
            or "ဘာတွေရှိ" in msg_lower
            or "available" in msg_lower
    ):

        print("enter available model multi brand")

        for brand in target_brands:
            contexts.append(query_sqlite("brand_filter", brand))

        context = "\n\n".join(contexts)


    #  All Brands
    elif any(x in msg_lower for x in ["brand", "ဘာတံဆိပ်"]) and not target_brands:

        print("enter all brand")
        context = query_sqlite("all_brands")


    #  Price without brand
    elif ("အထက်" in msg_lower or "အောက်" in msg_lower):

        print("enter Pricefilter without brand")
        nums = re.findall(r'\d+', message)

        if nums:
            price_value = int(nums[0]) * 100000 if "သိန်း" in message else int(nums[0])

            if "အောက်" in msg_lower:
                context = query_sqlite("price_filter_max", price_value)
            else:
                context = query_sqlite("price_filter_min", price_value)


    # Vector fallback
    else:
        print("enter Vector fallback multi brand")

        docs_all = []

        if target_brands:
            for brand in target_brands:
                docs = vector_db.similarity_search(
                    search_query,
                    k=3,
                    filter={"brand": brand},
                )
                docs_all.extend(docs)
        else:
            docs_all = vector_db.similarity_search(search_query, k=5)

        context = "\n".join([d.page_content for d in docs_all])

    # 3. Final Response Prompt
    final_prompt = f"""
သင်သည် ယဉ်ကျေးပျူငှာသော မြန်မာဖုန်းအရောင်းဝန်ထမ်း ဖြစ်သည်။
အောက်ပါ Context ကိုသာ အခြေခံ၍ ဝယ်သူကို လိုရင်းသာ ဖြေကြားပေးပါ။
စာကြောင်းများကို ထပ်ခါတလဲလဲ မပြောပါနှင့်။
မြန်မာဘာသာစကားသာသုံးပါ။
Thai, Korea, India, Chinese, Japanese and other ဘာသာစကားတွေ မသုံးပါနဲ့။
စာလုံးပေါင်းသတ်ပုံမှန်ကန်အောင်သုံးပါ။

လိုက်နာရမည့်စည်းကမ်းများ:
- Context ထဲမှာ မပါရင် မခန့်မှန်းပါနဲ့။
- User မေးထားသော သီးသန့် Model ({search_query}) နှင့်သာ ဆိုင်သော အချက်အလက်ကို ဦးစားပေး ဖြေကြားပါ။
- မဆိုင်သော Model များကို ထည့်မပြောပါနှင့်။
- မသေချာရင် "မရှိပါ/မသေချာပါ" လို့ပြောပါ
- ဖုန်း brand name ကိုပြည့်စုံစွာပြောပါ
- user မေးခွန်းမှာပါဝင်တဲ့ specifications နဲ့ကိုက်ညီတဲ့ ဖုန်းအားလုံးပြပါ
- အချက်အလက် နည်းပါက တိုက်ရိုက်ယဉ်ကျေးစွာ ဖြေကြားပါ

Context:
{context}

User Question:
{message}

မြန်မာလို ယဉ်ကျေးစွာ ဖြေကြားပေးပါ။
"""

    return final_prompt
