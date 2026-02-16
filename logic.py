"""
╔══════════════════════════════════════════════════════════════════════════╗
║           ULTIMATE RAG SYSTEM - v6.0 REFACTORED                         ║
║           Enhanced with RAM/Storage/Color + Strict Data Boundaries      ║
║                                                                          ║
║  NEW FEATURES:                                                           ║
║  ✓ RAM/Storage search support                                          ║
║  ✓ Color search support                                                 ║
║  ✓ Technical support intent (LLM knowledge allowed)                    ║
║  ✓ STRICT data source boundaries (no hallucination)                    ║
║                                                                          ║
║  DATA SOURCE RULES:                                                      ║
║  • Product queries → Database ONLY                                      ║
║  • CRM questions → shop_policies.py ONLY                               ║
║  • Technical support → LLM general knowledge OK                        ║
║  • Clear attribution when data not available                           ║
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

# Import the NEW enhanced classifier
from advanced_intent_classifier import (
    HybridIntentClassifier,
    Intent,
    llm_classify_intent,
    is_database_intent,
    is_policy_intent,
    is_technical_support_intent
)

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
    format='''%(asctime)s - %(levelname)s - %(message)s''',
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
    MAX_CONTEXT_TOKENS = 22150
    ENABLE_COMPRESSION = True


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE - COMPLETE DATA RETRIEVAL WITH NEW FIELDS
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
    """Get ALL products with new fields"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT brand, model, price, quantity, specifications, best_for, ram_storage, color 
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
            SELECT brand, model, price, quantity, specifications, best_for, ram_storage, color 
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
        spec_keyword: str = None,
        ram_storage: str = None,  # NEW
        color: str = None  # NEW
) -> List[Dict]:
    """Filter products with multiple criteria including RAM/storage and color"""
    with get_db_connection() as conn:
        query = """
            SELECT brand, model, price, quantity, specifications, best_for, ram_storage, color 
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

        # NEW: RAM/Storage filtering
        if ram_storage:
            query += " AND LOWER(ram_storage) LIKE ?"
            params.append(f"%{ram_storage.lower()}%")

        # NEW: Color filtering
        if color:
            query += " AND LOWER(color) LIKE ?"
            params.append(f"%{color.lower()}%")

        query += " ORDER BY brand, price ASC"

        cursor = conn.execute(query, params)
        products = [dict(row) for row in cursor.fetchall()]

    logger.info(f"🔍 Filtered: {len(products)} products")
    return products


# ═══════════════════════════════════════════════════════════════════════════
# ENTITY EXTRACTION - ENHANCED WITH RAM/STORAGE AND COLOR
# ═══════════════════════════════════════════════════════════════════════════

class EntityExtractor:
    """Multi-strategy entity extraction with RAM/storage and color support"""

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
            products = get_all_products()
            self._models_cache = [f"{p['brand']} {p['model']}" for p in products]
        return self._models_cache

    def extract_ram_storage(self, text: str) -> Optional[str]:
        """Extract RAM/storage specifications from text

        Examples:
        - "8GB RAM" -> "8GB"
        - "256GB storage" -> "256GB"
        - "8/256" -> "8/256"
        - "12GB RAM 512GB" -> "12GB"
        """
        text_lower = text.lower()

        # Pattern 1: Direct GB/TB mentions with RAM/ROM keywords
        patterns = [
            r'(\d+\s*(?:gb|tb))[\s/]*(?:ram|ရမ်|memory)',
            r'(?:ram|ရမ်|memory)[\s/]*(\d+\s*(?:gb|tb))',
            r'(\d+\s*(?:gb|tb))[\s/]*(?:storage|rom|ရုမ်|internal)',
            r'(?:storage|rom|ရုမ်|internal)[\s/]*(\d+\s*(?:gb|tb))',
            r'(\d+)[\s/]*(?:gb|ဂျီဘီ)',  # Myanmar
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                spec = match.group(1).strip()
                # Normalize spacing
                spec = re.sub(r'\s+', '', spec)
                return spec

        return None

    def extract_color(self, text: str) -> Optional[str]:
        """Extract color from text

        Examples:
        - "black phone" -> "black"
        - "အနီရောင်" -> "red"
        """
        text_lower = text.lower()

        # English colors
        english_colors = {
            'black': 'black',
            'white': 'white',
            'blue': 'blue',
            'red': 'red',
            'green': 'green',
            'gold': 'gold',
            'silver': 'silver',
            'pink': 'pink',
            'purple': 'purple',
            'gray': 'gray',
            'grey': 'gray',
            'yellow': 'yellow',
            'orange': 'orange',
        }

        # Myanmar colors
        myanmar_colors = {
            'နက်': 'black',
            'အဖြူ': 'white',
            'အပြာ': 'blue',
            'အနီ': 'red',
            'အစိမ်း': 'green',
            'ရွှေ': 'gold',
            'ငွေ': 'silver',
            'ပန်း': 'pink',
            'ခရမ်း': 'purple',
        }

        # Check English colors
        for color_word, color_name in english_colors.items():
            if re.search(rf'{color_word}', text_lower):
                return color_name

        # Check Myanmar colors
        for color_word, color_name in myanmar_colors.items():
            if color_word in text:
                return color_name

        return None

    def extract(self, text: str) -> Tuple[List[str], List[str], float]:
        """Extract brands and models with confidence score"""
        brands = []
        models = []

        # Try fuzzy matching if available
        if Config.ENABLE_FUZZY and FUZZY_AVAILABLE:
            # Brand matching
            brand_matches = process.extract(
                text,
                self.brands,
                scorer=fuzz.partial_ratio,
                limit=3
            )
            brands = [m[0] for m in brand_matches if m[1] >= Config.FUZZY_THRESHOLD]

            # Model matching
            model_matches = process.extract(
                text,
                self.models,
                scorer=fuzz.token_set_ratio,
                limit=5
            )
            models = [m[0] for m in model_matches if m[1] >= Config.FUZZY_THRESHOLD]

        # Fallback to simple matching
        if not brands and not models:
            text_lower = text.lower()
            brands = [b for b in self.brands if b.lower() in text_lower]
            models = [m for m in self.models if m.lower() in text_lower]

        confidence = 1.0 if (brands or models) else 0.0

        return brands, models, confidence


entity_extractor = EntityExtractor()


def parse_price_range(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse price range from text"""
    text_lower = text.lower()

    # Pattern: "under X lakh" or "X သိန်းအောက်"
    under_match = re.search(r'(under|below|less\s+than|အောက်).*?(\d+)[\s]*(lakh|သိန်း)', text_lower)
    if under_match:
        amount = int(under_match.group(2))
        return None, amount * 100000

    # Pattern: "X to Y lakh" or "X မှ Y သိန်း"
    range_match = re.search(r'(\d+)[\s]*(to|မှ|-)[\s]*(\d+)[\s]*(lakh|သိန်း)', text_lower)
    if range_match:
        min_amt = int(range_match.group(1))
        max_amt = int(range_match.group(3))
        return min_amt * 100000, max_amt * 100000

    # Pattern: "X lakh"
    exact_match = re.search(r'(\d+)[\s]*(lakh|သိန်း)', text_lower)
    if exact_match:
        amount = int(exact_match.group(1))
        # Assume "around X lakh" means X-20% to X+20%
        center = amount * 100000
        return int(center * 0.8), int(center * 1.2)

    return None, None


# ═══════════════════════════════════════════════════════════════════════════
# QUERY UNDERSTANDING WITH NEW FIELDS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class QueryUnderstanding:
    """Complete query understanding with RAM/storage and color"""
    intent: Intent
    standalone_query: str
    brands: List[str] = field(default_factory=list)
    models: List[str] = field(default_factory=list)
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    spec_keyword: Optional[str] = None
    ram_storage: Optional[str] = None  # NEW
    color: Optional[str] = None  # NEW
    confidence: float = 0.0


def llm_understand_query(message: str, history: List[Dict], llm, fast_intent: Intent) -> QueryUnderstanding:
    """Deep query understanding with LLM - enhanced for RAM/storage and color"""

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
  "intent": "brand_list|model_list|price_filter|spec_search|ram_storage_search|color_search|comparison|recommendation|stock_check|technical_support|followup|unknown",
  "brands": ["brand1", "brand2"],
  "models": ["model1"],
  "price_min": null or number,
  "price_max": null or number,
  "spec_keyword": "camera" or "battery" or "gaming" or null,
  "ram_storage": "8GB" or "256GB" or "8/256" or null,
  "color": "black" or "white" or "blue" or null,
  "confidence": 0.0 to 1.0
}}

RULES:
- brand_list: User wants ALL brands available
- model_list: User wants ALL models of a specific brand
- price_filter: Extract budget constraints
- ram_storage_search: Extract RAM/storage specs (e.g., "8GB RAM", "256GB storage")
- color_search: Extract color preference
- technical_support: Phone usage help, troubleshooting (NOT product info)
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
            ram_storage=result.get("ram_storage"),  # NEW
            color=result.get("color"),  # NEW
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
# FORMATTING - WITH NEW FIELDS
# ═══════════════════════════════════════════════════════════════════════════

def format_price(price: int) -> str:
    if price >= 100000:
        lakh = price // 100000
        rem = price % 100000
        thou_10 = rem // 10000
        thou_1 = (rem % 10000) // 1000

        result = f"{lakh} သိန်း"
        if thou_10 > 0:
            result += f" {thou_10} သောင်း"
        if thou_1 > 0:
            result += f" {thou_1} ထောင်"
        return result

    return f"{price:,} ကျပ်"


def format_product_full(p: Dict) -> str:
    """Full product formatting with RAM/storage and color"""
    ram_storage_info = p.get('ram_storage', 'N/A')
    color_info = p.get('color', 'N/A')

    return f"""📱 {p['brand']} {p['model']}
   💰 ဈေး: {format_price(p['price'])}
   📦 လက်ကျန်: {p['quantity']} လုံး
   💾 RAM/Storage: {ram_storage_info}
   🎨 အရောင်: {color_info}
   ⚙️ အချက်အလက်: {p['specifications']}
   ✨ သင့်လျော်: {p['best_for']}"""


def format_product_compact(p: Dict) -> str:
    """Compact product formatting"""
    stock = "✅ ရှိ" if p['quantity'] > 0 else "❌ ကုန်"
    ram_storage = p.get('ram_storage', '')
    ram_info = f" [{ram_storage}]" if ram_storage and ram_storage != 'N/A' else ""
    return f"📱 {p['brand']} {p['model']}{ram_info} - {format_price(p['price'])} ({stock})"


# ═══════════════════════════════════════════════════════════════════════════
# CONTEXT BUILDER - WITH STRICT DATA BOUNDARIES
# ═══════════════════════════════════════════════════════════════════════════

def build_context_complete(understanding: QueryUnderstanding) -> str:
    """Build complete context based on intent with STRICT data boundaries"""

    intent = understanding.intent

    # ========================================
    # CRM QUESTION - ONLY shop policies
    # ========================================
    if intent == Intent.CRM_QUESTION:
        if POLICIES_AVAILABLE:
            category = detect_policy_category(understanding.standalone_query)
            policy_text = get_policy(category)
            logger.info(f"📋 CRM Policy: {category}")
           # return policy_text
            return f"""# ❌ DO NOT recommend specific phone models {policy_text}"""
        else:
            return "တိုတောင်း၍ ယဉ်ကျေးစွာ ဖြေကြားပေးပါ။❌ DO NOT recommend specific phone models"

    # ========================================
    # TECHNICAL SUPPORT - Can use LLM knowledge
    # ========================================
    if intent == Intent.TECHNICAL_SUPPORT:
        # Return minimal context - LLM can use general knowledge
        return f"""# Technical Support Request:
User needs help with: {understanding.standalone_query}

You may use general knowledge about phone usage, settings, and troubleshooting.
This is NOT a product query - you can provide general technical guidance."""

    # ========================================
    # GREETING / CASUAL - No context
    # ========================================
    if intent in [Intent.GREETING, Intent.CASUAL]:
        return ""

    # ========================================
    # BRAND LIST - Show ALL brands (DATABASE ONLY)
    # ========================================
    if intent == Intent.BRAND_LIST:
        brands = get_all_brands()
        products = get_all_products()

        brand_info = {}
        for p in products:
            b = p['brand']
            if b not in brand_info:
                brand_info[b] = {'count': 0, 'min': p['price'], 'max': p['price']}
            brand_info[b]['count'] += 1
            brand_info[b]['min'] = min(brand_info[b]['min'], p['price'])
            brand_info[b]['max'] = max(brand_info[b]['max'], p['price'])

        context = "# ရရှိနိုင်သော Brand အားလုံး (DATABASE ONLY):\n\n"
        for b in sorted(brands):
            if b in brand_info:
                info = brand_info[b]
                context += f"📱 {b.upper()}: {info['count']} မော်ဒယ် "
                context += f"({format_price(info['min'])} - {format_price(info['max'])})\n"

        context += f"\n💡 စုစုပေါင်း: {len(products)} မော်ဒယ်\n"
        context += "CRITICAL: Show ONLY these brands from database. DO NOT add any brands not listed here."
        return context

    # ========================================
    # MODEL LIST - Show ALL models (DATABASE ONLY)
    # ========================================
    if intent == Intent.MODEL_LIST:
        brand = understanding.brands[0] if understanding.brands else None
        if not brand:
            return "Brand မသတ်မှတ်ရသေးပါ။"

        models = get_models_by_brand(brand)
        if not models:
            return f"{brand.upper()} မော်ဒယ်များ DATABASE တွင် မရှိပါ။"

        context = f"# {brand.upper()} မော်ဒယ် အားလုံး ({len(models)} မော်ဒယ်) - DATABASE ONLY:"
        for m in models:
            context += format_product_full(m) + ""

        context += "⚠️ CRITICAL: Show ONLY these models from database. DO NOT add colors, specs, or models not listed."
        return context

    # ========================================
    # PRICE FILTER (DATABASE ONLY)
    # ========================================
    if intent == Intent.PRICE_FILTER:
        products = filter_products(
            brands=understanding.brands if understanding.brands else None,
            price_min=understanding.price_min,
            price_max=understanding.price_max
        )

        if not products:
            return "ဒီဈေးနှုန်းအတွင်း ဖုန်း DATABASE တွင် မရှိပါ။"

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

        context = f"# {price_str} ဖုန်းများ ({len(products)} မော်ဒယ်) - DATABASE ONLY:"
        context += f"💡 {len(by_brand)} Brand ရှိပါသည်"

        for brand in sorted(by_brand.keys()):
            context += f"## {brand.upper()} ({len(by_brand[brand])} မော်ဒယ်):"
            for p in by_brand[brand]:
                context += format_product_compact(p) + ""
            context += ""

        context += "⚠️ CRITICAL: Show ONLY products within this price range from database."
        return context

    # ========================================
    # RAM/STORAGE SEARCH (NEW - DATABASE ONLY)
    # ========================================
    if intent == Intent.RAM_STORAGE_SEARCH:
        products = filter_products(
            ram_storage=understanding.ram_storage
        )

        if not products:
            ram_spec = understanding.ram_storage or "requested specification\n"
            return f"{ram_spec} နဲ့ကိုက်ညီတဲ့ ဖုန်း DATABASE တွင် မရှိပါ။\n"

        by_brand = defaultdict(list)
        for p in products:
            by_brand[p['brand']].append(p)

        context = f"# {understanding.ram_storage} ပါသော ဖုန်းများ ({len(products)} မော်ဒယ်) - DATABASE ONLY:\n"
        context += f"💡 {len(by_brand)} Brand ရှိပါသည်\n"

        for brand in sorted(by_brand.keys()):
            context += f"## {brand.upper()} ({len(by_brand[brand])} မော်ဒယ်):\n"
            for p in by_brand[brand]:
                context += format_product_full(p) + ""

        context += "⚠️ CRITICAL: Show ONLY phones with this RAM/storage from database.DO NOT invent specs or colors."
        return context

    # ========================================
    # COLOR SEARCH (NEW - DATABASE ONLY)
    # ========================================
    if intent == Intent.COLOR_SEARCH:
        products = filter_products(
            color=understanding.color
        )

        if not products:
            color_name = understanding.color or "requested color"
            return f"{color_name} အရောင် DATABASE တွင် မရှိပါ။"

        by_brand = defaultdict(list)
        for p in products:
            by_brand[p['brand']].append(p)

        context = f"# {understanding.color} အရောင် ဖုန်းများ ({len(products)} မော်ဒယ်) - DATABASE ONLY:"
        context += f"💡 {len(by_brand)} Brand ရှိပါသည်"

        for brand in sorted(by_brand.keys()):
            context += f"## {brand.upper()} ({len(by_brand[brand])} မော်ဒယ်):"
            for p in by_brand[brand]:
                context += format_product_full(p) + ""

        context += f"⚠️ CRITICAL: Show ONLY {understanding.color} phones from database. DO NOT suggest other colors."
        return context

    # ========================================
    # COMPARISON (DATABASE ONLY)
    # ========================================
    if intent == Intent.COMPARISON:
        models = understanding.models
        products = filter_products(models=models)

        if len(products) < 2:
            return "နှိုင်းယှဉ်ရန် မော်ဒယ် အနည်းဆုံး ၂ ခု DATABASE တွင် လိုအပ်ပါသည်။"

        context = "# နှိုင်းယှဉ်ချက် - DATABASE ONLY:"
        for p in products:
            context += "=" * 60 + ""
            context += format_product_full(p) + ""

        context += "⚠️ CRITICAL: Compare ONLY using specs from database. DO NOT add features not listed."
        return context

    # ========================================
    # STOCK CHECK (DATABASE ONLY)
    # ========================================
    if intent == Intent.STOCK_CHECK:
        models = understanding.models
        products = filter_products(models=models)

        if not products:
            return "မေးမြန်းထားသော မော်ဒယ် DATABASE တွင် မရှိပါ။"

        context = "# လက်ကျန် စစ်ဆေးချက် - DATABASE ONLY:"
        for p in products:
            status = "✅ ရှိသည်" if p['quantity'] > 0 else "❌ ကုန်သည်"
            context += f"📱 {p['brand']} {p['model']}: {status} ({p['quantity']} လုံး)"

        context += "⚠️ CRITICAL: Report ONLY stock status from database. DO NOT guess availability.DO NOT invent specs or colors."
        return context

    # ========================================
    # SPEC SEARCH / RECOMMENDATION - Hybrid (DATABASE + VECTOR)
    # ========================================
    if intent in [Intent.SPEC_SEARCH, Intent.RECOMMENDATION]:
        # SQL filtering
        products = filter_products(
            brands=understanding.brands if understanding.brands else None,
            price_min=understanding.price_min,
            price_max=understanding.price_max,
            spec_keyword=understanding.spec_keyword,
            ram_storage=understanding.ram_storage,
            color=understanding.color
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
            by_brand = defaultdict(list)
            for p in products:
                by_brand[p['brand']].append(p)

            spec_str = understanding.spec_keyword or "သင့်လျော်သော"
            context += f"# {spec_str.upper()} ဖုန်းများ ({len(products)} မော်ဒယ်) - DATABASE ONLY:"
            context += f"💡 {len(by_brand)} Brand ရှိပါသည်"

            # Show top 3 per brand for recommendations
            for brand in sorted(by_brand.keys()):
                context += f"## {brand.upper()}:"
                for p in by_brand[brand][:3]:
                    context += format_product_full(p) + ""

        if vector_docs:
            context += "# အသေးစိတ် အချက်အလက် (from vector database):"
            for doc in vector_docs[:5]:
                context += doc + ""

        if not context:
            return "သင့်လျော်သော ဖုန်း DATABASE တွင် မတွေ့ရှိပါ။"

        context += "⚠️ CRITICAL: Recommend ONLY phones from database. DO NOT invent specs or colors."
        return context

    # ========================================
    # GENERAL / UNKNOWN - Vector search
    # ========================================
    vector_db = get_vector_store()
    if vector_db:
        try:
            docs = vector_db.similarity_search(understanding.standalone_query, k=8)
            if docs:
                context = "# သက်ဆိုင်သော အချက်အလက် (from vector database):"
                for doc in docs:
                    context += doc.page_content + ""
                return context
        except:
            pass

    return "အချက်အလက် DATABASE တွင် မတွေ့ရှိပါ။"


def compress_context(context: str, max_tokens: int = 22150) -> str:
    """Compress context if too large"""
    if not Config.ENABLE_COMPRESSION:
        return context

    estimated_tokens = len(context) / 4
    if estimated_tokens <= max_tokens:
        return context

    logger.info(f"🗜️  Compressing: {estimated_tokens:.0f} → {max_tokens} tokens")
    max_chars = max_tokens * 4
    return context[:max_chars] + "... (အချက်အလက် အချို့ ဖြုတ်ထားသည်)"


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT BUILDER - WITH STRICT DATA SOURCE BOUNDARIES
# ═══════════════════════════════════════════════════════════════════════════

# REPLACE THIS FUNCTION IN logic.py (lines 844-1024)
# This is the CRITICAL fix to prevent LLM hallucination

def build_prompt(understanding: QueryUnderstanding, context: str, user_info: str = "") -> str:
    """Build prompt with EXPLICIT product inventory to prevent hallucination"""

    personalization = f"\nစကားပြောနေသူ: {user_info}" if user_info else ""

    # ========================================
    # GREETING / CASUAL - Keep as is
    # ========================================
    if understanding.intent == Intent.GREETING:
        return f"""သင်သည် Shwee Shaung Mobile ၏ အရောင်းဝန်ထမ်း ဖြစ်သည်။{personalization}

User: {understanding.standalone_query}

တိုတောင်း၍ ယဉ်ကျေးစွာ နှုတ်ဆက်ပါ။"""

    if understanding.intent == Intent.CASUAL:
        return f"""သင်သည် Shwee Shaung Mobile ၏ အရောင်းဝန်ထမ်း ဖြစ်သည်။{personalization}

User: {understanding.standalone_query}

ယဉ်ကျေးစွာ ဖြေကြားပါ။"""

    # ========================================
    # CRM QUESTION - Shop policies only
    # ========================================
    if understanding.intent == Intent.CRM_QUESTION:
        if context:
            return f"""သင်သည် {SHOP_INFO.get('name_myanmar', 'Shwee Shaung Mobile')} ၏ အရောင်းဝန်ထမ်း ဖြစ်သည်။{personalization}

User မေးခွန်း: {understanding.standalone_query}

ဆိုင်မူဝါဒ:
{context}

⚠️ CRITICAL: Use ONLY information from shop policies above.
DO NOT use general knowledge. If not in policies, say you don't have that information.
And also answer short to the main points.
မြန်မာလို ရှင်းလင်းစွာ ဖြေကြားပေးပါ။"""
        else:
            return f"""သင်သည် Shwee Shaung Mobile ၏ အရောင်းဝန်ထမ်း ဖြစ်သည်။{personalization}

User: {understanding.standalone_query}

ဒီအချက်အလက်က database မှာ မရှိပါဘူး။ ဆိုင်ကို 09-671698821 သို့ ဆက်သွယ်နိုင်ပါတယ်။"""

    # ========================================
    # TECHNICAL SUPPORT - Can use general knowledge
    # ========================================
    if understanding.intent == Intent.TECHNICAL_SUPPORT:
        return f"""သင်သည် Shwee Shaung Mobile ၏ အရောင်းဝန်ထမ်း ဖြစ်ပြီး ဖုန်းအသုံးပြုနည်းကို ကူညီပေးနိုင်သည်။{personalization}

User မေးခွန်း: {understanding.standalone_query}

{context}

✅ SPECIAL RULE: For technical support, you MAY use general phone knowledge
✅ Provide helpful troubleshooting steps
❌ DO NOT recommend specific phone models unless asked

မြန်မာလို ကူညီပေးပါ။"""

    # ========================================
    # DATABASE-DRIVEN INTENTS - THIS IS CRITICAL
    # ========================================

    # Get ALL products from database to show LLM
    all_products = get_all_products()

    # BUILD EXPLICIT INVENTORY LIST
    inventory_section = "=" * 70 + "\n"
    inventory_section += "🏪 SHWEE SHAUNG MOBILE - COMPLETE INVENTORY\n"
    inventory_section += "သင့်ဆိုင်တွင် ရှိသော ဖုန်းများ (ALL AVAILABLE PHONES IN DATABASE)\n"
    inventory_section += "=" * 70 + "\n\n"

    if all_products:
        # Group by brand for clarity
        from collections import defaultdict
        by_brand = defaultdict(list)
        for p in all_products:
            by_brand[p['brand']].append(p)

        for brand, products in sorted(by_brand.items()):
            inventory_section += f"\n【{brand}】 - {len(products)} models\n"
            inventory_section += "-" * 60 + "\n"

            for p in sorted(products, key=lambda x: x['price']):
                line = f"  • {p['model']} - {p['price']:,} MMK"

                if p.get('ram_storage'):
                    line += f" | RAM/Storage: {p['ram_storage']}"
                if p.get('color'):
                    line += f" | Color: {p['color']}"

                inventory_section += line + "\n"

        inventory_section += "\n" + "=" * 70 + "\n"
        inventory_section += f"📊 TOTAL: {len(all_products)} products in database\n"
        inventory_section += "=" * 70 + "\n\n"
    else:
        inventory_section += "⚠️ NO PRODUCTS IN DATABASE\n\n"

    # STRICT RULES SECTION
    strict_rules = """
🚨🚨🚨 ABSOLUTE MANDATORY RULES - ZERO TOLERANCE 🚨🚨🚨

【RULE 1: DATABASE-ONLY RESPONSES】
✅ You can ONLY mention brands/models from the inventory list above
✅ Every brand you mention MUST be in the inventory above
✅ Every model you mention MUST be in the inventory above
✅ Every price you mention MUST match the inventory above
✅ Every color you mention MUST be in the inventory above
❌ NEVER use your general knowledge about phones
❌ NEVER mention brands not in inventory (e.g., if iPhone not in list, don't mention it)
❌ NEVER invent specifications, colors, or prices
❌ NEVER recommend phones not in the inventory above

【RULE 2: IF NOT IN DATABASE】
If user asks about a brand/model NOT in inventory above:
→ Say: "Shwee Shaung Mobile မှာ [brand/model] မရှိပါဘူး"
→ Suggest: "ဆိုင်တွင် ရှိတဲ့ အခြား ဖုန်းများကို ကြည့်ရှုနိုင်ပါတယ်"
→ DO NOT provide any specs/info about that phone

【RULE 3: VALIDATION CHECKLIST】
Before sending your response, verify:
□ Every brand I mentioned is in the inventory above? (YES/NO)
□ Every model I mentioned is in the inventory above? (YES/NO)  
□ Every price I mentioned matches inventory above? (YES/NO)
□ I didn't use my training knowledge about phones? (YES/NO)

If ANY answer is NO → Rewrite response using ONLY inventory above

【RULE 4: RESPONSE FORMAT】
✅ Use Myanmar language naturally
✅ Use English for technical terms (camera, battery, charging, etc.)
✅ Show exact prices from inventory (e.g., 459,000 MMK, not "around 5 lakhs")
✅ Be helpful and friendly
❌ Don't write unnecessary notes or disclaimers
"""

    # Intent-specific instructions
    intent_instructions = {
        Intent.BRAND_LIST: """
【USER WANTS】: List of all brands
【YOUR TASK】:
  - List ALL brands from inventory above (not from your memory)
  - Show model count for each brand
  - Show price range for each brand
  - Example: "Samsung - 5 models (350,000 - 890,000 MMK)"
""",
        Intent.MODEL_LIST: """
【USER WANTS】: Models of a specific brand
【YOUR TASK】:
  - Show ALL models of that brand from inventory above
  - Include price and RAM/Storage for each
  - Sort by price (low to high)
  - If brand not in inventory → say "Shwee Shaung Mobile မှာ [brand] မရှိပါဘူး"
""",
        Intent.PRICE_FILTER: """
【USER WANTS】: Phones in a price range
【YOUR TASK】:
  - Show ALL phones in that price range from inventory above
  - Include different brands if available
  - Show exact prices from inventory
  - Sort by price
""",
        Intent.RAM_STORAGE_SEARCH: """
【USER WANTS】: Phones with specific RAM/Storage
【YOUR TASK】:
  - Show ONLY phones matching RAM/Storage from inventory above
  - Include brand, model, exact price
  - If no match → say "Shwee Shaung Mobile မှာ [spec] ပါတဲ့ ဖုန်း မရှိပါဘူး"
""",
        Intent.COLOR_SEARCH: """
【USER WANTS】: Phones in specific color
【YOUR TASK】:
  - Show ONLY phones with that color from inventory above
  - If color not in inventory → say "အဲဒီ အရောင် မရှိပါဘူး"
  - Don't suggest colors not in inventory
""",
        Intent.RECOMMENDATION: """
【USER WANTS】: Phone recommendation
【YOUR TASK】:
  - Recommend 3-5 phones from inventory above
  - Mix different brands if possible
  - Explain why each is suitable based on inventory specs
  - NEVER recommend phones not in inventory
""",
        Intent.COMPARISON: """
【USER WANTS】: Compare phones
【YOUR TASK】:
  - Compare ONLY phones from inventory above
  - Use actual specs from inventory
  - If comparing phone not in inventory → say it's not available
""",
        Intent.SPEC_SEARCH: """
【USER WANTS】: Phones with specific feature
【YOUR TASK】:
  - Show phones from inventory that match the feature
  - Use specs from inventory only
  - If no match → say feature not available in current stock
""",
        Intent.STOCK_CHECK: """
【USER WANTS】: Check if phone available
【YOUR TASK】:
  - Check inventory above
  - If found → show price and stock
  - If not found → say "Shwee Shaung Mobile မှာ မရှိပါဘူး"
""",
    }

    instruction = intent_instructions.get(understanding.intent, "")

    # BUILD FINAL PROMPT
    final_prompt = f"""သင်သည် Shwee Shaung Mobile ၏ အရောင်းဝန်ထမ်း ဖြစ်သည်။{personalization}

{inventory_section}

{strict_rules}

{instruction}

【ADDITIONAL CONTEXT FROM DATABASE】:
{context}

【USER QUESTION】: {understanding.standalone_query}

⚠️ Remember: You can ONLY talk about phones in the inventory above. If a phone is not listed in the inventory, you must say it's not available. Do NOT use your general knowledge about phones.
-Prioritize Directness: Provide only the most concise and direct answer to the user's query.
-Contextual Accuracy: If the answer is present within the provided context, extract and provide that specific information only.
-Strict Boundary (IMPORTANT): If the answer is found, DO NOT include any follow-up suggestions, shop phone numbers, or addresses. Stop the response immediately after providing the factual answer.
-Fallback Logic: Only if the context contains zero relevant information should you state, "တိကျတဲ့အချက်အလက် ရှာမတွေ့ပါဘူး" followed by the shop's contact details and address.
-Prohibited Content: Remove all conversational fillers, unnecessary pleasantries, advice, and proactive suggestions.
-Answer short to the main points.
-မြန်မာလို ယဉ်ကျေးစွာ ဖြေကြားပေးပါ။"""

    return final_prompt


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
    """Cache entry with timestamp"""
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
            "cache_hit_rate": f"{self.cache_hits / self.total * 100:.1f}%",
            "llm_call_rate": f"{self.llm_calls / self.total * 100:.1f}%",
            "intent_distribution": dict(self.by_intent),
        }


_metrics = Metrics()

# Initialize the hybrid classifier
hybrid_classifier = HybridIntentClassifier()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def get_final_prompt(message: str, history: list, llm, user_info: str = "") -> str:
    """
    ULTIMATE system with STRICT data source boundaries

    Data Source Rules:
    - Product queries → Database ONLY (no hallucination)
    - CRM questions → shop_policies.py ONLY
    - Technical support → LLM general knowledge OK
    """

    start_time = time.time()
    used_cache = False
    used_llm = False
    fetched_context = False

    try:
        logger.info(f"\n{'=' * 60}\n📩 Query: {message}\n{'=' * 60}")

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
        def use_llm_for_classification(msg):
            return llm_classify_intent(msg, llm)

        fast_intent, confidence = hybrid_classifier.classify(
            message,
            has_history=len(history) > 0,
            use_llm=use_llm_for_classification
        )

        logger.info(f"🎯 Intent: {fast_intent.value} (confidence: {confidence:.2f})")
        logger.info(f"   - Database intent: {is_database_intent(fast_intent)}")
        logger.info(f"   - Policy intent: {is_policy_intent(fast_intent)}")
        logger.info(f"   - Tech support intent: {is_technical_support_intent(fast_intent)}")

        # If confidence is too low, ask for clarification
        if confidence < 0.4:
            logger.warning(f"Low confidence classification: {fast_intent.value}")

        # ========================================
        # STEP 3: Entity Extraction (Enhanced)
        # ========================================
        brands, models, entity_conf = entity_extractor.extract(message)
        price_min, price_max = parse_price_range(message)

        # NEW: Extract RAM/storage and color
        ram_storage = entity_extractor.extract_ram_storage(message)
        color = entity_extractor.extract_color(message)

        logger.info(f"🔍 Entities: brands={brands}, models={models}, conf={entity_conf:.2f}")
        if ram_storage:
            logger.info(f"💾 RAM/Storage: {ram_storage}")
        if color:
            logger.info(f"🎨 Color: {color}")

        # ========================================
        # STEP 4: Query Understanding
        # ========================================
        # Simple intents - skip LLM
        if fast_intent in [Intent.GREETING, Intent.CASUAL, Intent.CRM_QUESTION, Intent.TECHNICAL_SUPPORT]:
            understanding = QueryUnderstanding(
                intent=fast_intent,
                standalone_query=message,
                confidence=1.0
            )
        # Complex or uncertain - use LLM
        elif fast_intent == Intent.UNKNOWN or entity_conf < 0.5:
            used_llm = True
            understanding = llm_understand_query(message, history, llm, fast_intent)
            # Merge extracted entities
            understanding.brands = list(set(understanding.brands + brands))
            understanding.models = list(set(understanding.models + models))
            if price_min:
                understanding.price_min = price_min
            if price_max:
                understanding.price_max = price_max
            if ram_storage and not understanding.ram_storage:
                understanding.ram_storage = ram_storage
            if color and not understanding.color:
                understanding.color = color
        # Use fast results
        else:
            understanding = QueryUnderstanding(
                intent=fast_intent,
                standalone_query=message,
                brands=brands,
                models=models,
                price_min=price_min,
                price_max=price_max,
                ram_storage=ram_storage,
                color=color,
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
        # STEP 7: Build Prompt with STRICT boundaries
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
                    f"{elapsed:.0f}ms\n{'=' * 60}\n")

        return final_prompt

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)

        return f"""သင်သည် မြန်မာဖုန်းဆိုင် အရောင်းဝန်ထမ်း ဖြစ်သည်။

User: {message}

စနစ်တွင် ယာယီ ပြဿနာရှိနေပါသည်။ နောက်တစ်ကြိမ် ထပ်မေးကြည့်ပါ။"""


def get_final_prompt_with_understanding(message: str, history: list, llm, user_info: str = "") -> Tuple[
    str, QueryUnderstanding]:
    """
    Modified version that returns both prompt and understanding object
    Needed for validation
    """
    start_time = time.time()
    used_cache = False
    used_llm = False
    fetched_context = False

    # Initialize these to None or empty so they exist if an error occurs early
    final_prompt = ""
    understanding = None

    try:
        logger.info(f"\n{'=' * 60}\n📩 Query: {message}\n{'=' * 60}")

        # ========================================
        # STEP 1: Check Cache
        # ========================================
        cached = _cache.get(message, len(history))
        if cached:
            used_cache = True
            logger.info(f"💾 CACHE HIT")
            _metrics.log(Intent.UNKNOWN, True, False, False)
            # Assuming the cache returns the (prompt, understanding) tuple
            return cached

        # ========================================
        # STEP 2: Fast Intent Classification
        # ========================================
        def use_llm_for_classification(msg):
            return llm_classify_intent(msg, llm)

        fast_intent, confidence = hybrid_classifier.classify(
            message,
            has_history=len(history) > 0,
            use_llm=use_llm_for_classification
        )

        logger.info(f"🎯 Intent: {fast_intent.value} (confidence: {confidence:.2f})")

        # ========================================
        # STEP 3: Entity Extraction (Enhanced)
        # ========================================
        brands, models, entity_conf = entity_extractor.extract(message)
        price_min, price_max = parse_price_range(message)
        ram_storage = entity_extractor.extract_ram_storage(message)
        color = entity_extractor.extract_color(message)

        # ========================================
        # STEP 4: Query Understanding
        # ========================================
        # Handle ordering intents specially - they don't need context building
        if fast_intent in [Intent.GREETING, Intent.CASUAL, Intent.CRM_QUESTION, Intent.TECHNICAL_SUPPORT,
                          Intent.BUY_PRODUCT, Intent.CART_COMMAND, Intent.ORDER_INPUT]:
            understanding = QueryUnderstanding(
                intent=fast_intent,
                standalone_query=message,
                brands=brands,  # Still extract brands/models for BUY_PRODUCT
                models=models,
                confidence=1.0
            )
        elif fast_intent == Intent.UNKNOWN or entity_conf < 0.5:
            used_llm = True
            understanding = llm_understand_query(message, history, llm, fast_intent)
            understanding.brands = list(set(understanding.brands + brands))
            understanding.models = list(set(understanding.models + models))
            if price_min: understanding.price_min = price_min
            if price_max: understanding.price_max = price_max
            if ram_storage and not understanding.ram_storage:
                understanding.ram_storage = ram_storage
            if color and not understanding.color:
                understanding.color = color
        else:
            understanding = QueryUnderstanding(
                intent=fast_intent,
                standalone_query=message,
                brands=brands,
                models=models,
                price_min=price_min,
                price_max=price_max,
                ram_storage=ram_storage,
                color=color,
                confidence=entity_conf
            )

        # ========================================
        # STEP 5: Context Retrieval (Skip for ordering intents)
        # ========================================
        context = ""

        # Skip context building for ordering intents - they're handled by order_manager
        if fast_intent in [Intent.BUY_PRODUCT, Intent.CART_COMMAND, Intent.ORDER_INPUT]:
            logger.info(f"⏭️ Skipping context for ordering intent: {fast_intent.value}")
            context = ""
        elif _memory.can_reuse_context(understanding.intent):
            context = _memory.last_context
        else:
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
        _cache.set((final_prompt, understanding), message, len(history))
        _metrics.log(understanding.intent, used_cache, used_llm, fetched_context)

        elapsed = (time.time() - start_time) * 1000
        logger.info(f"✅ Done: {understanding.intent.value} | {elapsed:.0f}ms\n{'=' * 60}\n")

    except Exception as e:
        logger.error(f"❌ Error in query processing: {str(e)}")
        # Provide fallback behavior or re-raise
        if understanding is None:
            understanding = QueryUnderstanding(intent=Intent.UNKNOWN, standalone_query=message)
        final_prompt = message

    return final_prompt, understanding


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