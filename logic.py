"""
╔══════════════════════════════════════════════════════════════════════════╗
║           ULTIMATE RAG SYSTEM - v5.0 FINAL                               ║
║           Advanced Techniques + Complete Outputs                         ║
║                                                                          ║
║  COMBINES:                                                               ║
║  ✓ Hybrid Retrieval (SQL + Vector Fusion)                              ║
║  ✓ Intent-Aware Processing                                              ║
║  ✓ Multi-Level Caching (TTL + Memory)                                   ║
║  ✓ Query Decomposition                                                  ║
║  ✓ Context Compression                                                  ║
║                                                                          ║
║  WITH PERFECT OUTPUTS:                                                   ║
║  ✓ Show ALL brands when asked                                           ║
║  ✓ Show ALL models when asked                                           ║
║  ✓ Complete price filtering with brand diversity                        ║
║  ✓ Complex queries with comprehensive data                              ║
║  ✓ NO unnecessary explanations - just complete facts                    ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import os
import re
import time
import json
import sqlite3
import logging
import hashlib
from typing import List, Dict, Optional, Tuple, Set, Any
from functools import lru_cache
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from collections import OrderedDict, defaultdict
from enum import Enum

import pandas as pd
import numpy as np
from dotenv import load_dotenv

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from shop_policies import get_policy, detect_policy_category, SHOP_INFO, POLICIES_AVAILABLE

# Fuzzy matching
try:
    from rapidfuzz import fuzz, process
    FUZZY_AVAILABLE = True
except ImportError:
    fuzz = None
    process = None
    FUZZY_AVAILABLE = False
    logging.warning("rapidfuzz not available - fuzzy matching disabled")

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class Config:
    """Configuration combining performance and completeness"""
    BASE_PATH = os.getenv("BASE_PATH")
    SQLITE_PATH = os.path.join(BASE_PATH, "phones.db")
    CHROMA_PATH = os.path.join(BASE_PATH, "chroma_db_v3")
    NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

    # Model settings
    EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

    # Output policy - SHOW EVERYTHING
    SHOW_ALL_BRANDS = True
    SHOW_ALL_MODELS = True
    MAX_PRODUCTS_TO_SHOW = 150  # All inventory

    # Performance settings
    CACHE_SIZE = 1000
    CACHE_TTL_SECONDS = 3600  # 1 hour

    # Retrieval settings
    VECTOR_SEARCH_K = 10
    ENABLE_HYBRID_SEARCH = True
    ENABLE_FUZZY = FUZZY_AVAILABLE
    FUZZY_THRESHOLD = 85

    # Context management
    MAX_CONTEXT_TOKENS = 3000
    ENABLE_COMPRESSION = True



# ═══════════════════════════════════════════════════════════════════════════
# INTENT TAXONOMY
# ═══════════════════════════════════════════════════════════════════════════

class Intent(str, Enum):
    """Intent types"""
    # No DB needed
    GREETING = "greeting"
    CASUAL = "casual"
    CRM_QUESTION = "crm_question"

    # DB needed - SHOW ALL policy
    BRAND_LIST = "brand_list"
    MODEL_LIST = "model_list"
    PRICE_FILTER = "price_filter"
    SPEC_SEARCH = "spec_search"
    COMPARISON = "comparison"
    RECOMMENDATION = "recommendation"
    STOCK_CHECK = "stock_check"

    # Follow-up
    FOLLOWUP = "followup"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE - COMPLETE DATA RETRIEVAL
# ═══════════════════════════════════════════════════════════════════════════

@contextmanager
def get_db_connection():
    """Database connection context manager"""
    conn = sqlite3.connect(Config.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_all_brands() -> List[str]:
    """Get ALL brands"""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT DISTINCT brand FROM products ORDER BY brand")
        brands = [row[0] for row in cursor.fetchall()]
    logger.info(f"📊 Brands: {len(brands)}")
    return brands


def get_all_products() -> List[Dict]:
    """Get ALL products"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT brand, model, price, quantity, specifications, best_for 
            FROM products 
            ORDER BY brand, price ASC
        """)
        products = [dict(row) for row in cursor.fetchall()]
    logger.info(f"📊 Total products: {len(products)}")
    return products


def get_models_by_brand(brand: str) -> List[Dict]:
    """Get ALL models for a brand"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT brand, model, price, quantity, specifications, best_for 
            FROM products 
            WHERE LOWER(brand) = LOWER(?)
            ORDER BY price ASC
        """, (brand,))
        models = [dict(row) for row in cursor.fetchall()]
    logger.info(f"📱 {brand}: {len(models)} models")
    return models


def filter_products(
    brands: List[str] = None,
    models: List[str] = None,
    price_min: int = None,
    price_max: int = None,
    spec_keyword: str = None
) -> List[Dict]:
    """Filter products with multiple criteria"""
    with get_db_connection() as conn:
        query = """
            SELECT brand, model, price, quantity, specifications, best_for 
            FROM products 
            WHERE 1=1
        """
        params = []

        if brands:
            placeholders = ','.join('?' * len(brands))
            query += f" AND LOWER(brand) IN ({placeholders})"
            params.extend([b.lower() for b in brands])

        if models:
            placeholders = ','.join('?' * len(models))
            query += f" AND LOWER(model) IN ({placeholders})"
            params.extend([m.lower() for m in models])

        if price_min is not None:
            query += " AND price >= ?"
            params.append(price_min)

        if price_max is not None:
            query += " AND price <= ?"
            params.append(price_max)

        if spec_keyword:
            query += " AND (LOWER(specifications) LIKE ? OR LOWER(best_for) LIKE ?)"
            pattern = f"%{spec_keyword.lower()}%"
            params.extend([pattern, pattern])

        query += " ORDER BY brand, price ASC"

        cursor = conn.execute(query, params)
        products = [dict(row) for row in cursor.fetchall()]

    logger.info(f"🔍 Filtered: {len(products)} products")
    return products


# ═══════════════════════════════════════════════════════════════════════════
# ENTITY EXTRACTION - ADVANCED
# ═══════════════════════════════════════════════════════════════════════════

class EntityExtractor:
    """Multi-strategy entity extraction"""

    def __init__(self):
        self._brands_cache = None
        self._models_cache = None

    @property
    def brands(self) -> List[str]:
        if self._brands_cache is None:
            self._brands_cache = get_all_brands()
        return self._brands_cache

    @property
    def models(self) -> List[str]:
        if self._models_cache is None:
            with get_db_connection() as conn:
                cursor = conn.execute("SELECT DISTINCT LOWER(model) FROM products")
                self._models_cache = sorted([row[0] for row in cursor.fetchall()],
                                          key=len, reverse=True)
        return self._models_cache

    def extract(self, text: str) -> Tuple[List[str], List[str], float]:
        """Extract brands and models"""
        text_lower = text.lower()
        brands_found = []
        models_found = []
        confidence = 0.0

        # Regex matching
        for brand in self.brands:
            if re.search(r'\b' + re.escape(brand.lower()) + r'\b', text_lower):
                brands_found.append(brand)
                confidence = 1.0

        for model in self.models:
            if re.search(r'\b' + re.escape(model) + r'\b', text_lower):
                models_found.append(model)
                confidence = 1.0

        # Fuzzy matching if no exact match
        if Config.ENABLE_FUZZY and not (brands_found or models_found) and FUZZY_AVAILABLE:
            brand_matches = process.extract(
                text_lower, self.brands,
                scorer=fuzz.token_set_ratio,
                limit=2,
                score_cutoff=Config.FUZZY_THRESHOLD
            )
            if brand_matches:
                brands_found = [m[0] for m in brand_matches]
                confidence = brand_matches[0][1] / 100.0

            model_matches = process.extract(
                text_lower, self.models,
                scorer=fuzz.token_set_ratio,
                limit=2,
                score_cutoff=Config.FUZZY_THRESHOLD - 5
            )
            if model_matches:
                models_found = [m[0] for m in model_matches]
                confidence = max(confidence, model_matches[0][1] / 100.0)

        return list(set(brands_found)), list(set(models_found)), confidence


entity_extractor = EntityExtractor()


# ═══════════════════════════════════════════════════════════════════════════
# PRICE PARSING
# ═══════════════════════════════════════════════════════════════════════════

import re
import logging
from typing import Tuple, Optional

# Setup logger (သင့် code ထဲမှာ ရှိပြီးသားဖြစ်နိုင်ပါတယ်)
logger = logging.getLogger(__name__)


def parse_price_range(text: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Parse Myanmar price expressions with support for:
    - Myanmar Digits (သိန်း၂၀, ၂၀သိန်း)
    - English Digits (သိန်း 20, 20 သိန်း)
    - Myanmar Number Words (သိန်းနှစ်ဆယ်, နှစ်ဆယ်သိန်း)
    - Directional Keywords (အောက်, အထက်, ကျော်, မကျော်)
    """
    text_lower = text.lower()

    # ၁။ မြန်မာဂဏန်းမှ အင်္ဂလိပ်ဂဏန်းသို့ ပြောင်းရန် Table
    mm_digits = str.maketrans('၀၁၂၃၄၅၆၇၈၉', '0123456789')

    # ၂။ မြန်မာစာသား ကိန်းဂဏန်းများ
    mm_nums = {
        'တစ်': 1, 'နှစ်': 2, 'သုံး': 3, 'လေး': 4, 'ငါး': 5,
        'ခြောက်': 6, 'ခုနစ်': 7, 'ရှစ်': 8, 'ကိုး': 9, 'ဆယ်': 10
    }

    price_min = None
    price_max = None

    # 'သိန်း' ပါဝင်မှသာ ရှာဖွေမည်
    if 'သိန်း' in text_lower:
        value = 0

        # က။ ဂဏန်းပါမပါ အရင်စစ်မည် (ဥပမာ- သိန်း၂၀ သို့မဟုတ် ၂၀သိန်း)
        # Regex: သိန်း အရှေ့ သို့မဟုတ် အနောက်တွင် ကပ်လျက်ရှိသော ဂဏန်းကို ရှာသည်
        digit_match = re.search(r'သိန်း\s*([၀-၉\d]+)|([၀-၉\d]+)\s*သိန်း', text_lower)

        if digit_match:
            # Match ဖြစ်သော group (၁ သို့မဟုတ် ၂) ကိုယူပြီး အင်္ဂလိပ်ဂဏန်းပြောင်းမည်
            val_str = (digit_match.group(1) or digit_match.group(2)).translate(mm_digits)
            value = int(val_str) * 100000
        else:
            # ခ။ စာသား (Text) ဖြင့်လာသော ဈေးနှုန်းများကို တွက်ချက်မည် (ဥပမာ- နှစ်ဆယ်သိန်း)
            temp_val = 0
            # စာသားများကို တစ်လုံးချင်းစစ်ပြီး ပေါင်းစပ်မည်
            for word, num in mm_nums.items():
                if word in text_lower:
                    if word == 'ဆယ်':
                        # 'နှစ်ဆယ်' ဆိုလျှင် ၂ x ၁၀ ဖြစ်အောင် လုပ်ပေးသည်
                        temp_val = (temp_val * 10) if temp_val > 0 else 10
                    else:
                        temp_val = num

            # ဘာစာသားမှ ရှာမတွေ့လျှင် Default ၁ သိန်း သတ်မှတ်မည်
            value = temp_val * 100000 if temp_val > 0 else 100000

        # ၃။ Direction Logic (Range, Max သို့မဟုတ် Min သတ်မှတ်ခြင်း)
        # ဈေးနှုန်း အနိမ့်/အမြင့် ခွဲခြားရန် Keyword များ
        is_under = any(w in text_lower for w in ['အောက်', 'under', 'below', 'less', 'နဲ့ရ', 'နဲ့ဝယ်', 'မကျော်'])
        is_above = any(w in text_lower for w in ['အထက်', 'above', 'over', 'more', 'ကျော်'])
        is_between = any(w in text_lower for w in ['between', 'to', 'မှ', 'နဲ့'])

        if is_under:
            price_max = value
        elif is_above:
            price_min = value
        elif is_between:
            # Range ရှာရန် logic (ဥပမာ- ၁၀ သိန်း နဲ့ ၂၀ သိန်းကြား)
            numbers = re.findall(r'([၀-၉\d]+)', text_lower)
            if len(numbers) >= 2:
                n1 = int(numbers[0].translate(mm_digits)) * 100000
                n2 = int(numbers[1].translate(mm_digits)) * 100000
                price_min, price_max = min(n1, n2), max(n1, n2)
            else:
                price_max = value
        else:
            # Default အနေဖြင့် Max ဟု ယူဆမည်
            price_max = value

    logger.info(f"💰 Parsed Price: min={price_min}, max={price_max}")
    return price_min, price_max


# ═══════════════════════════════════════════════════════════════════════════
# FAST INTENT CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════

# Import the advanced classifier
from advanced_intent_classifier import HybridIntentClassifier, llm_classify_intent

# Create global classifier instance
hybrid_classifier = HybridIntentClassifier()

# ═══════════════════════════════════════════════════════════════════════════
# LLM QUERY UNDERSTANDING
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class QueryUnderstanding:
    """Complete query understanding"""
    intent: Intent
    standalone_query: str
    brands: List[str] = field(default_factory=list)
    models: List[str] = field(default_factory=list)
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    spec_keyword: Optional[str] = None
    confidence: float = 0.0


def llm_understand_query(message: str, history: List[Dict], llm, fast_intent: Intent) -> QueryUnderstanding:
    """Deep query understanding with LLM"""

    history_str = ""
    if history:
        for msg in history[-5:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_str += f"{role}: {msg['content'][:100]}\n"

    prompt = f"""Analyze this Myanmar phone shop query. Return ONLY valid JSON.

History:
{history_str}

Query: {message}

Return JSON:
{{
  "standalone_query": "Rewritten standalone query in Myanmar",
  "intent": "brand_list|model_list|price_filter|spec_search|comparison|recommendation|stock_check|followup|unknown",
  "brands": ["brand1", "brand2"],
  "models": ["model1"],
  "price_min": null or number,
  "price_max": null or number,
  "spec_keyword": "camera" or "battery" or "gaming" or null,
  "confidence": 0.0 to 1.0
}}

RULES:
- brand_list: User wants ALL brands available
- model_list: User wants ALL models of a specific brand
- price_filter: Extract budget constraints
- For followup: Resolve references from history
- standalone_query MUST be Myanmar language

Return ONLY JSON:"""

    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        content = re.sub(r'```json\s*|\s*```', '', content)
        result = json.loads(content)

        understanding = QueryUnderstanding(
            intent=Intent(result.get("intent", fast_intent.value)),
            standalone_query=result.get("standalone_query", message),
            brands=result.get("brands", []),
            models=result.get("models", []),
            price_min=result.get("price_min"),
            price_max=result.get("price_max"),
            spec_keyword=result.get("spec_keyword"),
            confidence=result.get("confidence", 0.5)
        )

        logger.info(f"🧠 LLM: {understanding.intent.value}, conf={understanding.confidence:.2f}")
        return understanding
    except Exception as e:
        logger.error(f"LLM error: {e}")
        return QueryUnderstanding(
            intent=fast_intent,
            standalone_query=message,
            confidence=0.3
        )


# ═══════════════════════════════════════════════════════════════════════════
# VECTOR STORE
# ═══════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def get_vector_store():
    """Get vector store (cached)"""
    try:
        embeddings = HuggingFaceEmbeddings(model_name=Config.EMBEDDING_MODEL)
        return Chroma(persist_directory=Config.CHROMA_PATH, embedding_function=embeddings)
    except Exception as e:
        logger.error(f"Vector store error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# FORMATTING - COMPLETE DATA PRESENTATION
# ═══════════════════════════════════════════════════════════════════════════

def format_price(price: int) -> str:
    """Format price Myanmar style"""
    if price >= 100000:
        lakh = price // 100000
        remainder = price % 100000
        if remainder == 0:
            return f"{lakh} သိန်း"
        elif remainder >= 10000:
            man = remainder // 10000
            return f"{lakh} သိန်း {man} သောင်း"
        else:
            thou = remainder // 1000
            if thou > 0:
                return f"{lakh} သိန်း {thou} ထောင်"
            return f"{lakh} သိန်း"
    return f"{price:,} ကျပ်"


def format_product_full(p: Dict) -> str:
    """Full product formatting"""
    return f"""📱 {p['brand']} {p['model']}
   💰 ဈေး: {format_price(p['price'])}
   📦 လက်ကျန်: {p['quantity']} လုံး
   ⚙️ အချက်အလက်: {p['specifications']}
   ✨ သင့်လျော်: {p['best_for']}"""


def format_product_compact(p: Dict) -> str:
    """Compact product formatting"""
    stock = "✅ ရှိ" if p['quantity'] > 0 else "❌ ကုန်"
    return f"📱 {p['brand']} {p['model']} - {format_price(p['price'])} ({stock})"


# ═══════════════════════════════════════════════════════════════════════════
# CONTEXT BUILDER - COMPLETE + HYBRID
# ═══════════════════════════════════════════════════════════════════════════

def build_context_complete(understanding: QueryUnderstanding) -> str:
    """Build complete context based on intent"""

    intent = understanding.intent

    # ========================================
    # CRM QUESTION - Load shop policies (FIRST!)
    # ========================================
    if intent == Intent.CRM_QUESTION:
        if POLICIES_AVAILABLE:
            # Detect which policy is needed
            category = detect_policy_category(understanding.standalone_query)
            policy_text = get_policy(category)

            logger.info(f"📋 CRM Policy: {category}")
            return policy_text
        else:
            # Fallback if policies file not available
            return "CRM အကြောင်း အထွေထွေ အချက်အလက်များကို ဖြေကြားပေးပါ။"

    # ========================================
    # GREETING / CASUAL - No context
    # ========================================
    if intent in [Intent.GREETING, Intent.CASUAL]:
        return ""


    # ========================================
    # BRAND LIST - Show ALL brands
    # ========================================
    if intent == Intent.BRAND_LIST:
        brands = get_all_brands()
        products = get_all_products()

        # Summarize by brand
        brand_info = {}
        for p in products:
            b = p['brand']
            if b not in brand_info:
                brand_info[b] = {'count': 0, 'min': p['price'], 'max': p['price']}
            brand_info[b]['count'] += 1
            brand_info[b]['min'] = min(brand_info[b]['min'], p['price'])
            brand_info[b]['max'] = max(brand_info[b]['max'], p['price'])

        context = "# ရရှိနိုင်သော Brand အားလုံး:\n\n"
        for b in sorted(brands):
            if b in brand_info:
                info = brand_info[b]
                context += f"📱 {b.upper()}: {info['count']} မော်ဒယ် "
                context += f"({format_price(info['min'])} - {format_price(info['max'])})\n"

        context += f"\n💡 စုစုပေါင်း: {len(products)} မော်ဒယ်\n"
        return context

    # ========================================
    # MODEL LIST - Show ALL models of brand
    # ========================================
    if intent == Intent.MODEL_LIST:
        brand = understanding.brands[0] if understanding.brands else None
        if not brand:
            return "Brand မသတ်မှတ်ရသေးပါ။"

        models = get_models_by_brand(brand)
        if not models:
            return f"{brand.upper()} မော်ဒယ်များ မရှိပါ။"

        context = f"# {brand.upper()} မော်ဒယ် အားလုံး ({len(models)} မော်ဒယ်):\n\n"
        for m in models:
            context += format_product_full(m) + "\n\n"

        return context

    # ========================================
    # PRICE FILTER - Show ALL in range
    # ========================================
    if intent == Intent.PRICE_FILTER:
        products = filter_products(
            brands=understanding.brands if understanding.brands else None,
            price_min=understanding.price_min,
            price_max=understanding.price_max
        )

        if not products:
            return "ဒီဈေးနှုန်းအတွင်း ဖုန်း မရှိပါ။"

        # Group by brand
        by_brand = defaultdict(list)
        for p in products:
            by_brand[p['brand']].append(p)

        price_str = ""
        if understanding.price_min:
            price_str += f"{format_price(understanding.price_min)} အထက်"
        if understanding.price_max:
            if price_str:
                price_str += f" မှ {format_price(understanding.price_max)} အောက်"
            else:
                price_str += f"{format_price(understanding.price_max)} အောက်"

        context = f"# {price_str} ဖုန်းများ ({len(products)} မော်ဒယ်):\n\n"
        context += f"💡 {len(by_brand)} Brand ရှိပါသည်\n\n"

        for brand in sorted(by_brand.keys()):
            context += f"## {brand.upper()} ({len(by_brand[brand])} မော်ဒယ်):\n"
            for p in by_brand[brand]:
                context += format_product_compact(p) + "\n"
            context += "\n"

        return context

    # ========================================
    # COMPARISON - Full specs
    # ========================================
    if intent == Intent.COMPARISON:
        models = understanding.models
        products = filter_products(models=models)

        if len(products) < 2:
            return "နှိုင်းယှဉ်ရန် မော်ဒယ် အနည်းဆုံး ၂ ခု လိုအပ်ပါသည်။"

        context = "# နှိုင်းယှဉ်ချက်:\n\n"
        for p in products:
            context += "=" * 60 + "\n"
            context += format_product_full(p) + "\n\n"

        return context

    # ========================================
    # STOCK CHECK
    # ========================================
    if intent == Intent.STOCK_CHECK:
        models = understanding.models
        products = filter_products(models=models)

        if not products:
            return "မေးမြန်းထားသော မော်ဒယ် မရှိပါ။"

        context = "# လက်ကျန် စစ်ဆေးချက်:\n\n"
        for p in products:
            status = "✅ ရှိသည်" if p['quantity'] > 0 else "❌ ကုန်သည်"
            context += f"📱 {p['brand']} {p['model']}: {status} ({p['quantity']} လုံး)\n"

        return context

    # ========================================
    # SPEC SEARCH / RECOMMENDATION - Hybrid
    # ========================================
    if intent in [Intent.SPEC_SEARCH, Intent.RECOMMENDATION]:
        # SQL filtering
        products = filter_products(
            brands=understanding.brands if understanding.brands else None,
            price_min=understanding.price_min,
            price_max=understanding.price_max,
            spec_keyword=understanding.spec_keyword
        )

        # Vector search for semantic matching
        vector_docs = []
        if Config.ENABLE_HYBRID_SEARCH:
            vector_db = get_vector_store()
            if vector_db:
                try:
                    docs = vector_db.similarity_search(
                        understanding.standalone_query,
                        k=Config.VECTOR_SEARCH_K
                    )
                    vector_docs = [d.page_content for d in docs]
                except:
                    pass

        # Combine
        context = ""

        if products:
            # Group by brand for recommendations
            by_brand = defaultdict(list)
            for p in products:
                by_brand[p['brand']].append(p)

            spec_str = understanding.spec_keyword or "သင့်လျော်သော"
            context += f"# {spec_str.upper()} ဖုန်းများ ({len(products)} မော်ဒယ်):\n\n"
            context += f"💡 {len(by_brand)} Brand ရှိပါသည်\n\n"

            # Show top 3 per brand for recommendations
            for brand in sorted(by_brand.keys()):
                context += f"## {brand.upper()}:\n"
                for p in by_brand[brand][:3]:
                    context += format_product_full(p) + "\n\n"

        if vector_docs:
            context += "\n# အသေးစိတ် အချက်အလက်:\n"
            for doc in vector_docs[:5]:
                context += doc + "\n\n"

        if not context:
            return "သင့်လျော်သော ဖုန်း မတွေ့ရှိပါ။"

        return context

    # ========================================
    # GENERAL / UNKNOWN - Vector search
    # ========================================
    vector_db = get_vector_store()
    if vector_db:
        try:
            docs = vector_db.similarity_search(understanding.standalone_query, k=8)
            if docs:
                context = "# သက်ဆိုင်သော အချက်အလက်:\n\n"
                for doc in docs:
                    context += doc.page_content + "\n\n"
                return context
        except:
            pass

    return "အချက်အလက် မတွေ့ရှိပါ။"


def compress_context(context: str, max_tokens: int = 3000) -> str:
    """Compress context if too large"""
    if not Config.ENABLE_COMPRESSION:
        return context

    estimated_tokens = len(context) / 4
    if estimated_tokens <= max_tokens:
        return context

    logger.info(f"🗜️  Compressing: {estimated_tokens:.0f} → {max_tokens} tokens")
    max_chars = max_tokens * 4
    return context[:max_chars] + "\n\n... (အချက်အလက် အချို့ ဖြုတ်ထားသည်)"


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT BUILDER - OUTPUT FOCUSED
# ═══════════════════════════════════════════════════════════════════════════

def build_prompt(understanding: QueryUnderstanding, context: str, user_info: str = "") -> str:
    """Build prompt for perfect outputs"""

    personalization = f"\nစကားပြောနေသူ: {user_info}" if user_info else ""

    # Greeting / Casual
    if understanding.intent == Intent.GREETING:
        return f"""သင်သည် မြန်မာဖုန်းဆိုင် အရောင်းဝန်ထမ်း ဖြစ်သည်။{personalization}

User: {understanding.standalone_query}

တိုတောင်း၍ ယဉ်ကျေးစွာ နှုတ်ဆက်ပါ။"""

    if understanding.intent == Intent.CASUAL:
        return f"""သင်သည် မြန်မာဖုန်းဆိုင် အရောင်းဝန်ထမ်း ဖြစ်သည်။{personalization}

User: {understanding.standalone_query}

ယဉ်ကျေးစွာ ဖြေကြားပါ။"""

    # Find the CRM prompt section and update it:

    if understanding.intent == Intent.CRM_QUESTION:
        if context:  # We have shop policies
            return f"""သင်သည် {SHOP_INFO.get('name_myanmar', 'မြန်မာဖုန်းဆိုင်')} ၏ အရောင်းဝန်ထမ်း ဖြစ်သည်။{personalization}

    User မေးခွန်း: {understanding.standalone_query}

    ဆိုင်မူဝါဒ:
    {context}

    ⚠️ အရေးကြီး:
    ✅မလိုအပ်သော စကားများ မပြောရ - အဖြေကို တိုက်ရိုက် ပြပေးပါ
    ✅ Context ထဲ မပါတာကို မခန့်မှန်းရ
    ✅ အထက်ပါ မူဝါဒအတိုင်း တိကျစွာ ဖြေကြားပါ
    ✅ မူဝါဒ၌ မပါသော အရာများကို မဖြေရ
    ✅ ဖုန်းနံပါတ်နှင့် လိပ်စာကို ပြည့်စုံစွာ ပေးပါ

    မြန်မာလို ရှင်းလင်းစွာ ဖြေကြားပေးပါ။"""
        else:  # Generic CRM answer
            return f"""သင်သည် မြန်မာဖုန်းဆိုင် အရောင်းဝန်ထမ်း ဖြစ်သည်။{personalization}
            မလိုအပ်သော စကားများ မပြောရ - အဖြေကို တိုက်ရိုက် ပြပေးပါ
            မြန်မာလို ရှင်းလင်းစွာ ဖြေကြားပါ။"""

    # Data-driven intents
    instructions = {
        Intent.BRAND_LIST: """
🎯 လုပ်ဆောင်ချက်:
- Context ထဲက Brand အားလုံးကို ပြပေးရမည်
- တစ်ခုမကျန် ဖော်ပြရမည်
- မော်ဒယ်အရေအတွက်နှင့် ဈေးနှုန်းအပိုင်းအခြား ပြပါ
-မေးခွန်းထဲတွင် Brands များကို လုံးဝ (လုံးဝ) ထပ်မဖြည့်ပါနှင့်။""",

        Intent.MODEL_LIST: """
🎯 လုပ်ဆောင်ချက်:
- Context ထဲက မော်ဒယ် အားလုံးကို ပြပေးရမည် တစ်ခုမှ မဖြုတ်ချရ
- Context ထဲ မပါတာကို မခန့်မှန်းရ""",

        Intent.PRICE_FILTER: """
🎯 လုပ်ဆောင်ချက်:
- Context ထဲက ဈေးနှုန်းအတွင်း ဖုန်း အားလုံးကို ပြပေးရမည် တစ်ခုမှ မဖြုတ်ချရ
- Brand အမျိုးမျိုး ပါရမည်
- Brand တစ်ခုတည်းကို မပြရ""",

        Intent.COMPARISON: """
🎯 လုပ်ဆောင်ချက်:
- နှိုင်းယှဉ်ချက် အသေးစိတ် ပြပေးရမည်
- အချက်အလက် အပြည့်အစုံ ပြရမည်
- ဘယ်ဟာ ပိုကောင်းသည် ရှင်းပြပါ""",

        Intent.RECOMMENDATION: """
🎯 လုပ်ဆောင်ချက်:
- Brand အမျိုးမျိုးမှ ရွေးချယ်စရာများ ပေးရမည်
- အနည်းဆုံး ၃ ခု အကြံပြုပါ
- အကြောင်းပြချက်နှင့် ရှင်းပြပါ""",
    }

    instruction = instructions.get(understanding.intent, "")

    return f"""သင်သည် မြန်မာဖုန်းဆိုင် အရောင်းဝန်ထမ်း ဖြစ်သည်။{personalization}
{instruction}

⚠️ အရေးကြီးဆုံး စည်းကမ်းများ:
✅စာကြောင်းများကို ထပ်ခါတလဲလဲ မပြောပါနှင့်။ မြန်မာဘာသာစကားသာသုံးပါ။ Thai, Korea, India, Chinese, Japanese and other ဘာသာစကားတွေ မသုံးပါနဲ့  
✅စာလုံးပေါင်းသတ်ပုံမှန်ကန်အောင်သုံးပါ။
✅ {context} ထဲက အချက်အလက် အတိုင်း အပြည့်အစုံ ပြပေးရမည်
✅ တစ်ခုမှ ဖြုတ်ချမပြရ
✅ Brand မျိုးစုံ ပါအောင် ပြပေးရမည်
✅ မလိုအပ်သော စကားများ မပြောရ - အဖြေကို တိုက်ရိုက် ပြပေးပါ
❌ Context ထဲ မပါတာကို မခန့်မှန်းရ

Context:
{context}

User Question: {understanding.standalone_query}

မြန်မာလို ယဉ်ကျေးစွာ ဖြေကြားပေးပါ။"""


# ═══════════════════════════════════════════════════════════════════════════
# CONVERSATION MEMORY
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ConversationMemory:
    """Conversation state with caching"""
    current_brands: Set[str] = field(default_factory=set)
    current_models: Set[str] = field(default_factory=set)
    last_intent: Optional[Intent] = None
    last_context: str = ""
    last_understanding: Optional[QueryUnderstanding] = None
    turn_count: int = 0

    def update(self, understanding: QueryUnderstanding, context: str):
        if understanding.brands:
            self.current_brands.update(understanding.brands)
        if understanding.models:
            self.current_models.update(understanding.models)
        self.last_intent = understanding.intent
        self.last_context = context
        self.last_understanding = understanding
        self.turn_count += 1

    def can_reuse_context(self, new_intent: Intent) -> bool:
        if not self.last_context:
            return False
        if new_intent == Intent.FOLLOWUP:
            return True
        if new_intent == self.last_intent and self.turn_count > 0:
            return True
        return False

    def clear(self):
        self.current_brands.clear()
        self.current_models.clear()
        self.last_intent = None
        self.last_context = ""
        self.last_understanding = None
        self.turn_count = 0


_memory = ConversationMemory()


# ═══════════════════════════════════════════════════════════════════════════
# CACHING WITH TTL
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CacheEntry:
    value: str
    timestamp: float

    def is_expired(self, ttl: int) -> bool:
        return time.time() - self.timestamp > ttl


class TTLCache:
    """Cache with TTL"""
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.cache: Dict[str, CacheEntry] = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl
        self.hits = 0
        self.misses = 0

    def _make_key(self, *args) -> str:
        combined = "||".join(str(a) for a in args)
        return hashlib.md5(combined.encode()).hexdigest()[:16]

    def get(self, *args) -> Optional[str]:
        key = self._make_key(*args)
        if key in self.cache:
            entry = self.cache[key]
            if not entry.is_expired(self.ttl):
                self.hits += 1
                self.cache.move_to_end(key)
                return entry.value
            del self.cache[key]
        self.misses += 1
        return None

    def set(self, value: str, *args):
        key = self._make_key(*args)
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = CacheEntry(value=value, timestamp=time.time())

    def clear(self):
        self.cache.clear()
        self.hits = 0
        self.misses = 0


_cache = TTLCache(max_size=Config.CACHE_SIZE, ttl=Config.CACHE_TTL_SECONDS)


# ═══════════════════════════════════════════════════════════════════════════
# METRICS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Metrics:
    total: int = 0
    cache_hits: int = 0
    llm_calls: int = 0
    context_fetches: int = 0
    by_intent: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def log(self, intent: Intent, used_cache: bool, used_llm: bool, fetched: bool):
        self.total += 1
        if used_cache:
            self.cache_hits += 1
        if used_llm:
            self.llm_calls += 1
        if fetched:
            self.context_fetches += 1
        self.by_intent[intent.value] += 1

    def report(self) -> Dict:
        if self.total == 0:
            return {"status": "No queries yet"}
        return {
            "total": self.total,
            "cache_hit_rate": f"{self.cache_hits/self.total*100:.1f}%",
            "llm_call_rate": f"{self.llm_calls/self.total*100:.1f}%",
            "intent_distribution": dict(self.by_intent),
        }


_metrics = Metrics()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def get_final_prompt(message: str, history: list, llm, user_info: str = "") -> str:
    """
    ULTIMATE system combining advanced RAG + complete outputs
    """

    start_time = time.time()
    used_cache = False
    used_llm = False
    fetched_context = False

    try:
        logger.info(f"\n{'='*60}\n📩 Query: {message}\n{'='*60}")

        # ========================================
        # STEP 1: Check Cache
        # ========================================
        cached = _cache.get(message, len(history))
        if cached:
            used_cache = True
            logger.info(f"💾 CACHE HIT")
            _metrics.log(Intent.UNKNOWN, True, False, False)
            return cached

        # ========================================
        # STEP 2: Fast Intent Classification
        # ========================================
        # New way - with LLM fallback
        def use_llm_for_classification(msg):
            return llm_classify_intent(msg, llm)

        fast_intent, confidence = hybrid_classifier.classify(
            message,
            has_history=len(history) > 0,
            use_llm=use_llm_for_classification
        )

        logger.info(f"Intent confidence: {confidence:.2f}")

        # If confidence is too low, you can ask for clarification
        if confidence < 0.4:
            logger.warning(f"Low confidence classification: {fast_intent.value}")

        # ========================================
        # STEP 3: Entity Extraction
        # ========================================
        brands, models, entity_conf = entity_extractor.extract(message)
        price_min, price_max = parse_price_range(message)

        logger.info(f"🔍 Entities: brands={brands}, models={models}, conf={entity_conf:.2f}")

        # ========================================
        # STEP 4: Query Understanding
        # ========================================
        # Simple intents - skip LLM
        if fast_intent in [Intent.GREETING, Intent.CASUAL, Intent.CRM_QUESTION]:
            understanding = QueryUnderstanding(
                intent=fast_intent,
                standalone_query=message,
                confidence=1.0
            )
        # Complex or uncertain - use LLM
        elif fast_intent == Intent.UNKNOWN or entity_conf < 0.5:
            used_llm = True
            understanding = llm_understand_query(message, history, llm, fast_intent)
            understanding.brands = list(set(understanding.brands + brands))
            understanding.models = list(set(understanding.models + models))
            if price_min:
                understanding.price_min = price_min
            if price_max:
                understanding.price_max = price_max
        # Use fast results
        else:
            understanding = QueryUnderstanding(
                intent=fast_intent,
                standalone_query=message,
                brands=brands,
                models=models,
                price_min=price_min,
                price_max=price_max,
                confidence=entity_conf
            )

        logger.info(f"🎯 Final Intent: {understanding.intent.value}")

        # ========================================
        # STEP 5: Context Retrieval
        # ========================================
        context = ""

        # Check if we can reuse
        if _memory.can_reuse_context(understanding.intent):
            logger.info("♻️  REUSING context")
            context = _memory.last_context
        # Fetch fresh
        else:
            logger.info("🔍 FETCHING context")
            fetched_context = True
            context = build_context_complete(understanding)
            context = compress_context(context, Config.MAX_CONTEXT_TOKENS)

        # ========================================
        # STEP 6: Update Memory
        # ========================================
        _memory.update(understanding, context)

        # ========================================
        # STEP 7: Build Prompt
        # ========================================
        final_prompt = build_prompt(understanding, context, user_info)

        # ========================================
        # STEP 8: Cache & Log
        # ========================================
        _cache.set(final_prompt, message, len(history))
        _metrics.log(understanding.intent, used_cache, used_llm, fetched_context)

        elapsed = (time.time() - start_time) * 1000
        logger.info(f"✅ Done: {understanding.intent.value} | "
                   f"LLM: {'✓' if used_llm else '✗'} | "
                   f"Context: {'fetched' if fetched_context else 'reused'} | "
                   f"{elapsed:.0f}ms\n{'='*60}\n")

        return final_prompt

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)

        return f"""သင်သည် မြန်မာဖုန်းဆိုင် အရောင်းဝန်ထမ်း ဖြစ်သည်။

User: {message}

စနစ်တွင် ယာယီ ပြဿနာရှိနေပါသည်။ နောက်တစ်ကြိမ် ထပ်မေးကြည့်ပါ။"""


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def get_router_metrics() -> Dict:
    """Get metrics"""
    return _metrics.report()


def reset_conversation():
    """Reset conversation"""
    _memory.clear()
    logger.info("🔄 Conversation reset")


def reset_all_metrics():
    """Reset all"""
    global _metrics, _cache, _memory
    _metrics = Metrics()
    _cache.clear()
    _memory.clear()
    logger.info("🔄 Full reset")