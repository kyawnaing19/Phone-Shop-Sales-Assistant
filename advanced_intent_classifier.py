"""
╔══════════════════════════════════════════════════════════════════════════╗
║              ADVANCED INTENT CLASSIFICATION SYSTEM - v2.0                ║
║              Enhanced for RAM/Storage & Color queries                    ║
║              Hybrid Approach: Rules + Embeddings + LLM                   ║
║                                                                          ║
║  UPDATES:                                                                ║
║  ✓ Added RAM/Storage search intent                                     ║
║  ✓ Added Color search intent                                           ║
║  ✓ Enhanced technical support detection                                ║
║  ✓ Stricter data source boundaries                                     ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from enum import Enum
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# INTENT DEFINITIONS WITH EXAMPLE QUERIES
# ═══════════════════════════════════════════════════════════════════════════

class Intent(str, Enum):
    """Intent types with detailed descriptions"""
    # No DB needed - Non-sales queries
    GREETING = "greeting"
    CASUAL = "casual"
    CRM_QUESTION = "crm_question"
    TECHNICAL_SUPPORT = "technical_support"  # NEW: For phone usage help

    # DB needed - Sales & Product queries
    BRAND_LIST = "brand_list"
    MODEL_LIST = "model_list"
    PRICE_FILTER = "price_filter"
    SPEC_SEARCH = "spec_search"
    RAM_STORAGE_SEARCH = "ram_storage_search"  # NEW
    COLOR_SEARCH = "color_search"  # NEW
    COMPARISON = "comparison"
    RECOMMENDATION = "recommendation"
    STOCK_CHECK = "stock_check"

    # Ordering intents - NEW
    BUY_PRODUCT = "buy_product"  # User wants to buy a specific product
    CART_COMMAND = "cart_command"  # Cart management (view, add, checkout)
    ORDER_INPUT = "order_input"  # User providing order details (address, phone, etc)

    # Follow-up
    FOLLOWUP = "followup"
    UNKNOWN = "unknown"


# Training examples for each intent (for semantic matching)
INTENT_EXAMPLES = {
    Intent.GREETING: [
        "hello", "hi", "hey", "good morning", "good afternoon",
        "မင်္ဂလာပါ", "မင်္ဂလာ", "ဟယ်လို", "နေကောင်းလား",
    ],

    Intent.CASUAL: [
        "how are you", "what's up", "thank you", "thanks", "ok", "okay",
        "နေကောင်းလား", "ကျေးဇူး", "အိုကေ", "ရပြီ",
    ],

    Intent.CRM_QUESTION: [
        "phone number", "contact number", "address", "location", "shop location",
        "opening hours", "closing time", "warranty", "return policy", "refund",
        "payment method", "how to pay", "support hours", "customer service",
        "ဖုန်းနံပါတ်", "ဆက်သွယ်ရန်", "လိပ်စာ", "ဘယ်မှာလဲ", "ဆိုင်လိပ်စာ",
        "ဆိုင်ဖွင့်ချိန်", "ပိတ်ချိန်", "အာမခံ", "ပြန်အမ်း", "ငွေပေးချေမှု",
        "အချက်အလက်လုံခြုံရေး", "ကူညီမှု", "ဝန်ဆောင်မှု",
    ],

    Intent.TECHNICAL_SUPPORT: [
        "how to use", "how to setup", "how to install", "how to transfer",
        "phone not working", "battery draining", "screen frozen", "wifi problem",
        "bluetooth issue", "camera not working", "app crashing", "update phone",
        "ဘယ်လို အသုံးပြုရမလဲ", "ဖုန်း ဘယ်လို သုံးရမလဲ", "setting ပြင်",
        "transfer လုပ်နည်း", "backup လုပ်နည်း", "ဖုန်း မလုပ်ဘူး",
        "battery သုံးပြီး", "screen အလုပ်မလုပ်", "wifi မတက်",
    ],

    Intent.BRAND_LIST: [
        "what brands", "show phones", "available phones", "all phones",
        "what phones do you have", "phone brands", "which brands",
        "ဘယ် brand တွေရှိလဲ", "ဖုန်းတွေ ပြပါ", "ဖုန်း ဘာတွေရှိလဲ",
        "အားလုံး ပြပါ", "brand အားလုံး",
    ],

    Intent.MODEL_LIST: [
        "samsung phones", "iphone models", "show samsung", "xiaomi phones",
        "oppo models", "vivo phones", "samsung ဘာတွေရှိလဲ", "iphone တွေ",
        "samsung မော်ဒယ်", "xiaomi ဖုန်းတွေ",
    ],

    Intent.PRICE_FILTER: [
        "under 5 lakh", "below 3 lakh", "phones under 500000", "budget 5 lakh",
        "5 သိန်းအောက်", "3 သိန်း အောက်", "ဈေးသက်သာတဲ့", "ဘတ်ဂျက် 5 သိန်း",
        "သိန်း 10 အောက်", "ငါးသိန်းနဲ့ဝယ်လို့ရမလား",
    ],

    Intent.SPEC_SEARCH: [
        "good camera phone", "long battery", "gaming phone", "camera ကောင်းတဲ့",
        "battery ကြာတဲ့", "ဂိမ်းဆော့ဖို့", "5G phone", "fast charging",
    ],

    Intent.RAM_STORAGE_SEARCH: [
        "8GB RAM", "256GB storage", "12GB RAM phone", "512GB storage",
        "8GB RAM နဲ့", "256GB ရှိတဲ့", "RAM 12GB", "storage ကြီးတဲ့",
        "memory ကြီးတဲ့", "internal storage", "ROM 256",
    ],

    Intent.COLOR_SEARCH: [
        "black phone", "white color", "blue phones", "red available",
        "နက်ရောင်", "အဖြူရောင်", "အပြာရောင်", "အနီရောင်",
        "ဘယ်အရောင်ရှိလဲ", "available colors", "color options",
    ],

    Intent.COMPARISON: [
        "compare iphone vs samsung", "difference between", "which is better",
        "iphone နဲ့ samsung ယှဉ်", "ဘယ်ဟာပိုကောင်းလဲ", "ခြားနားချက်",
    ],

    Intent.RECOMMENDATION: [
        "which phone should i buy", "recommend me", "best phone", "suggest",
        "ဘယ်ဖုန်း ဝယ်ရမလဲ", "အကြံပြုပါ", "အကောင်းဆုံး", "ရွေးပေးပါ",
    ],

    Intent.STOCK_CHECK: [
        "do you have", "available", "in stock", "ရှိလား", "ရနိုင်လား",
        "stock ရှိလား", "လက်ကျန်",
    ],

    Intent.BUY_PRODUCT: [
        "i want to buy", "i'll take", "want to purchase", "order this",
        "ဝယ်မယ်", "ယူမယ်", "order တင်မယ်", "ဝယ်ချင်တယ်",
        "အဲဒါ ဝယ်မယ်", "ဒါကို ဝယ်မယ်",
    ],

    Intent.CART_COMMAND: [
        "view cart", "show cart", "cart", "checkout",
        "add to cart", "add more", "continue shopping",
        "cart ကြည့်", "ဆက်ထည့်", "ထပ်ထည့်", "checkout လုပ်",
    ],

    Intent.ORDER_INPUT: [
        # This is detected by order state, not by keywords
        # Used when user is in ordering flow
    ],

    Intent.FOLLOWUP: [
        "that one", "this", "those", "the price", "how much",
        "အဲဒါ", "ဒါ", "သူ", "ဈေး", "ဘယ်လောက်",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# COMPREHENSIVE PATTERN MATCHING
# ═══════════════════════════════════════════════════════════════════════════

class RuleBasedClassifier:
    """
    Comprehensive rule-based classifier with extensive patterns
    Goal: Catch 90%+ of queries with rules alone
    """

    def __init__(self):
        self.patterns = self._build_comprehensive_patterns()

    def _build_comprehensive_patterns(self) -> Dict[Intent, List[str]]:
        """Build exhaustive pattern list"""
        return {
            Intent.GREETING: [
                r'^(hi|hello|hey|hola|greetings)(\s|!|\.|$)',
                r'^(good\s+(morning|afternoon|evening|night))',
                r'^မင်္ဂလာ',
                r'^ဟယ်လို',
            ],

            Intent.CASUAL: [
                r'(how\s+are\s+you|how.*doing|what.*up)',
                r'(thank|thanks|thx|grateful|appreciate)',
                r'^(ok|okay|sure|fine|alright|got\s+it)(\s|!|\.|$)',
                r'နေကောင်းလား',
                r'ကျေးဇူး',
                r'^(အိုကေ|ရပြီ)',
            ],

            Intent.CRM_QUESTION: [
                # Phone/Contact - EXPANDED
                r'(phone|mobile|telephone|call).*?(number|no|နံပါတ်)',
                r'(contact|reach|call).*?(number|info|details)',
                r'(ဖုန်း|မိုဘိုင်း).*(နံပါတ်|နံပတ်)',
                r'(ဆက်သွယ်|ခေါ်ဆို).*(ရန်|နံပါတ်)',
                r'(hotline|customer.*line)',

                # Address/Location - EXPANDED
                r'(address|location|place|where.*located)',
                r'(shop|store|branch).*(address|location|where)',
                r'(where.*shop|where.*store|where.*branch)',
                r'(map|direction|navigate|find.*shop)',
                r'(ဆိုင်|စတိုး).*(လိပ်စာ|နေရာ|ဘယ်မှာ)',
                r'(လိပ်စာ|တည်နေရာ|နေရာ)',
                r'(ဘယ်|ဘယ်မှာ|ဘယ်နား).*(ရှိ|လဲ|မှာ)',
                r'(map|မြေပုံ)',

                # Hours - EXPANDED
                r'(opening|closing|business|working).*?(hour|time|ချိန်)',
                r'(open|close|ဖွင့်|ပိတ်).*(time|hour|when|ချိန်)',
                r'(what.*time.*open|when.*open|schedule)',
                r'(ဆိုင်|shop).*(ဖွင့်|ပိတ်|အချိန်)',

                # Warranty - EXPANDED
                r'(warranty|guarantee|အာမခံ)',
                r'(how\s+long.*warranty|warranty.*period)',
                r'(repair|fix|service|ပြင်)',
                r'(broken|damage|defect|ပျက်)',

                # Return/Refund - EXPANDED
                r'(return|refund|exchange|ပြန်အမ်း|လဲလှယ်)',
                r'(money\s+back|get.*refund)',
                r'(can.*return|able.*return)',

                # Payment - EXPANDED
                r'(payment|pay|paid|ငွေ).*(method|way|how|option)',
                r'(accept.*card|take.*cash|use.*kbz)',
                r'(kbz|wave|cb.*pay|mobile.*banking)',
                r'(installment|အရစ်|လစဉ်)',
                r'(invoice|receipt|bill|ဘောင်ချာ)',

                # Support - EXPANDED
                r'(customer.*(service|support)|support.*team)',
                r'(help|assist|support|ကူညီ)',
                r'(problem|issue|complaint|ပြဿနာ|ကန့်ကွက်)',
                r'(talk.*(agent|person|human))',

                # Privacy - EXPANDED
                r'(privacy|private|personal|data)',
                r'(security|secure|safe|protected|လုံခြုံ)',
            ],

            Intent.TECHNICAL_SUPPORT: [
                # Usage & Setup
                r'(how\s+to|ဘယ်လို).*(use|သုံး|setup|install|config)',
                r'(how\s+do\s+i).*(transfer|backup|restore|sync)',
                r'(setting|ဆက်တင်).*(change|ပြင်|adjust)',

                # Troubleshooting
                r'(phone|ဖုန်း).*(not\s+working|problem|မလုပ်|ပျက်)',
                r'(battery|ဘက်ထရီ).*(drain|fast|သုံးပြီး|ကုန်)',
                r'(screen|မျက်နှာပြင်).*(frozen|black|stuck|freeze)',
                r'(wifi|ဝိုင်ဖိုင်).*(not\s+connect|problem|မတက်)',
                r'(bluetooth|ဘလူးတုသ်).*(not\s+work|issue)',
                r'(app|အက်ပ်).*(crash|close|freeze|ပိတ်သွား)',
                r'(camera|ကင်မရာ).*(not\s+work|blurry|မရှင်း)',

                # Software
                r'(update|အပ်ဒိတ်).*(software|system|phone)',
                r'(factory\s+reset|restore|ပြန်လည်သတ်မှတ်)',
                r'(how\s+to.*screenshot|screen\s+record)',
            ],

            Intent.BRAND_LIST: [
                r'(what|which).*(brand|phone|model).*(have|available|sell|ရှိ)',
                r'(show|list|display).*(all|every).*(phone|brand|model)',
                r'(available|ရှိတဲ့).*(brand|phone|ဖုန်း)',
                r'(ဘယ်|ဘာ).*(brand|ဖုန်း).*(တွေ|များ|ရှိ|လဲ)',
                r'(phone|ဖုန်း|mobile).*(အားလုံး|တွေ|များ)',
                r'(ဖုန်း.*ပြ|show.*phone)',
            ],

            Intent.MODEL_LIST: [
                r'(samsung|iphone|xiaomi|oppo|vivo|realme|huawei).*(model|phone|မော်ဒယ်|ဖုန်း)',
                r'(show|ပြ).*(samsung|iphone|xiaomi|oppo|vivo)',
                r'(samsung|iphone|xiaomi).*(ဘာတွေ|များ|တွေ)',
            ],

            Intent.PRICE_FILTER: [
                r'(under|below|less\s+than|အောက်).*(lakh|သိန်း|\d+)',
                r'(budget|price|ဈေး).*(range|under|between)',
                r'(\d+)\s*(lakh|သိန်း).*(under|below|အောက်)',
                r'(cheap|affordable|သက်သာ)',
            ],

            Intent.SPEC_SEARCH: [
                r'(camera|ကင်မရာ).*(good|best|ကောင်း|excellent)',
                r'(battery|ဘက်ထရီ).*(long|last|ကြာ|good)',
                r'(gaming|ဂိမ်း).*(phone|ဖုန်း)',
                r'(5g|4g).*(phone|support|network)',
                r'(fast\s+charg|quick\s+charg|မြန်တဲ့.*အားသွင်း)',
                r'(processor|chip|performance|အမြန်)',
            ],

            Intent.RAM_STORAGE_SEARCH: [
                # RAM patterns
                r'\b(\d+)\s*gb\s*(ram|ရမ်)\b',
                r'(ram|ရမ်|memory).*?(\d+)\s*gb',
                r'(\d+)\s*(gb|ဂျီဘီ).*(ram|ရမ်|memory)',

                # Storage patterns
                r'\b(\d+)\s*gb\s*(storage|rom|ရုမ်)\b',
                r'(storage|rom|ရုမ်|internal).*?(\d+)\s*gb',
                r'(\d+)\s*(gb|tb|ဂျီဘီ).*(storage|rom|ရုမ်)',

                # Combined
                r'(\d+)\s*gb.*?(\d+)\s*gb',  # e.g., "8GB 256GB"
                r'(memory|သိုလှောင်မှု).*(ကြီး|များ|large)',
            ],

            Intent.COLOR_SEARCH: [
                # English colors
                r'(black|white|blue|red|green|gold|silver|pink|purple).*(phone|color|available)',
                r'(phone|model).*(black|white|blue|red|green|gold|silver)',
                r'(available|come).*(color|အရောင်)',

                # Myanmar colors
                r'(နက်|အဖြူ|အပြာ|အနီ|အစိမ်း|ရွှေ|ငွေ|ပန်း|ခရမ်း).*(ရောင်|ရှိ)',
                r'(အရောင်|ရောင်).*(ဘယ်|ဘာ|တွေ|များ)',
                r'ဘယ်အရောင်ရှိလဲ',
            ],

            Intent.COMPARISON: [
                r'(compar|vs|versus).*(phone|model)',
                r'(difference|differ).*(between)',
                r'(which|ဘယ်).*(better|best|ကောင်း)',
                r'(iphone|samsung|xiaomi).*(vs|နဲ့|and).*(iphone|samsung|xiaomi)',
                r'ယှဉ်ကြည့်',
            ],

            Intent.RECOMMENDATION: [
                r'(which|what).*(should|recommend|suggest)',
                r'(best|top|ကောင်း).*(phone|choice|option)',
                r'(recommend|suggest|advice|အကြံပြု)',
                r'ဘယ်ဖုန်း.*ဝယ်',
            ],

            Intent.STOCK_CHECK: [
                r'(do\s+you\s+have|got|available)',
                r'(in\s+stock|stock|လက်ကျန်)',
                r'(ရှိ|ရ|ရနိုင်)လား',
            ],

            Intent.BUY_PRODUCT: [
                # Buy intent - MUST be specific
                r'(want|wanna|like).*(buy|purchase|order|get)',
                r'(buy|purchase|order).*(this|that|the)',
                r'(i\'ll|i\s+will).*(take|buy|get)',
                r'(ဝယ်|ယူ).*(မယ်|ချင်)',
                r'(order|အော်ဒါ).*(တင်|လုပ်)',
                r'(ဒါ|အဲဒါ|ဟို).*(ဝယ်|ယူ)',
            ],

            Intent.CART_COMMAND: [
                # Cart management keywords - STRICT
                r'(add\s+to\s+cart|add\s+more)',
                r'(view|show|check).*(cart|တောင်း)',
                r'(checkout|check\s+out)',
                r'cart',
                r'(ဆက်|ထပ်).*(ထည့်|ယူ)',
            ],

            Intent.FOLLOWUP: [
                r'^(that|this|those|these|it)(\s|$)',
                r'^(the\s+)?price',
                r'^(how\s+much)',
                r'^(အဲ|ဒါ|သူ|ဟို)',
            ],
        }

    def classify(self, message: str, has_history: bool = False) -> Tuple[Intent, float]:
        """
        Rule-based classification using pattern matching
        Returns: (intent, confidence_score)
        """
        msg_lower = message.lower()

        # Check each pattern
        for intent, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, msg_lower):
                    # Higher confidence for longer matches
                    confidence = min(0.9, 0.7 + (len(pattern) / 200))
                    logger.info(f"✅ Rule Match: {intent.value} (pattern: {pattern[:50]}...)")
                    return intent, confidence

        # Followup gets special treatment with history
        if has_history and len(message.split()) <= 3:
            logger.info(f"🔗 Likely followup (short message with history)")
            return Intent.FOLLOWUP, 0.6

        return Intent.UNKNOWN, 0.0


# ═══════════════════════════════════════════════════════════════════════════
# SEMANTIC CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════

class SemanticClassifier:
    """
    Keyword-based semantic matching
    Catches queries that don't match exact patterns
    """

    def __init__(self):
        self.intent_keywords = self._build_keyword_sets()

    def _build_keyword_sets(self) -> Dict[Intent, set]:
        """Convert examples to keyword sets"""
        keyword_sets = {}
        for intent, examples in INTENT_EXAMPLES.items():
            keywords = set()
            for example in examples:
                keywords.update(re.findall(r'\w+', example.lower()))
            keyword_sets[intent] = keywords
        return keyword_sets

    def classify(self, message: str) -> Tuple[Intent, float]:
        """
        Semantic classification using keyword overlap
        Returns: (intent, confidence_score)
        """
        msg_lower = message.lower()
        words = set(re.findall(r'\w+', msg_lower))

        best_intent = Intent.UNKNOWN
        best_score = 0.0

        for intent, keywords in self.intent_keywords.items():
            # Calculate overlap
            overlap = len(words & keywords)
            if overlap > 0:
                # Confidence = overlap / min(query_length, keyword_set_size)
                confidence = overlap / min(len(words), 10)

                if confidence > best_score:
                    best_score = confidence
                    best_intent = intent

        if best_score > 0.3:  # Threshold
            logger.info(f"🔍 Semantic Match: {best_intent.value} (conf={best_score:.2f})")
            return best_intent, best_score

        return Intent.UNKNOWN, 0.0


# ═══════════════════════════════════════════════════════════════════════════
# HYBRID INTENT CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════

class HybridIntentClassifier:
    """
    Combines multiple classification strategies:
    1. Rule-based (fast, high precision)
    2. Semantic similarity (catches missing keywords)
    3. LLM fallback (for complex cases)
    """

    def __init__(self):
        self.rule_classifier = RuleBasedClassifier()
        self.semantic_classifier = SemanticClassifier()
        self.stats = {
            'rule_based': 0,
            'semantic': 0,
            'llm': 0,
            'total': 0,
        }

    def classify(
            self,
            message: str,
            has_history: bool = False,
            use_llm: callable = None
    ) -> Tuple[Intent, float]:
        """
        Hybrid classification with confidence scoring

        Args:
            message: User message
            has_history: Whether conversation has history
            use_llm: Optional LLM function for fallback

        Returns:
            (intent, confidence)
        """
        self.stats['total'] += 1

        # ========================================
        # Strategy 1: Rule-based (FAST)
        # ========================================
        intent, confidence = self.rule_classifier.classify(message, has_history)

        if confidence >= 0.7:  # High confidence threshold
            self.stats['rule_based'] += 1
            logger.info(f"✅ Rule-based classification: {intent.value} (conf={confidence:.2f})")
            return intent, confidence

        # ========================================
        # Strategy 2: Semantic Similarity
        # ========================================
        sem_intent, sem_confidence = self.semantic_classifier.classify(message)

        if sem_confidence > confidence:
            intent = sem_intent
            confidence = sem_confidence

        if confidence >= 0.5:  # Medium confidence threshold
            self.stats['semantic'] += 1
            logger.info(f"✅ Semantic classification: {intent.value} (conf={confidence:.2f})")
            return intent, confidence

        # ========================================
        # Strategy 3: LLM Fallback (ACCURATE but SLOW)
        # ========================================
        if use_llm and confidence < 0.5:
            try:
                self.stats['llm'] += 1
                llm_intent, llm_confidence = use_llm(message)
                logger.info(f"✅ LLM classification: {llm_intent.value} (conf={llm_confidence:.2f})")
                return llm_intent, llm_confidence
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}")

        # ========================================
        # Fallback: Return best guess or UNKNOWN
        # ========================================
        if confidence > 0:
            logger.info(f"⚠️  Low confidence classification: {intent.value} (conf={confidence:.2f})")
            return intent, confidence

        logger.info(f"❌ Unable to classify: UNKNOWN")
        return Intent.UNKNOWN, 0.0

    def get_stats(self) -> Dict:
        """Get classification statistics"""
        if self.stats['total'] == 0:
            return {}

        return {
            'total': self.stats['total'],
            'rule_based': f"{self.stats['rule_based']} ({self.stats['rule_based'] / self.stats['total'] * 100:.1f}%)",
            'semantic': f"{self.stats['semantic']} ({self.stats['semantic'] / self.stats['total'] * 100:.1f}%)",
            'llm': f"{self.stats['llm']} ({self.stats['llm'] / self.stats['total'] * 100:.1f}%)",
        }


# ═══════════════════════════════════════════════════════════════════════════
# LLM FALLBACK CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════

def llm_classify_intent(message: str, llm) -> Tuple[Intent, float]:
    """
    Use LLM to classify intent when rules and semantic fail
    This is the most accurate but slowest method
    """

    prompt = f"""Classify this Myanmar phone shop query into ONE intent category.

Query: "{message}"

Intent categories:
- greeting: Greetings, hello
- casual: Casual chat, thank you, ok
- crm_question: Phone number, address, hours, warranty, payment, support, shop policies
- technical_support: How to use phone, troubleshooting, phone problems, settings help
- brand_list: What phones/brands available
- model_list: Show models of a specific brand
- price_filter: Phones within price range
- spec_search: Phones with specific features (camera, battery, gaming, processor)
- ram_storage_search: Phones with specific RAM or storage (e.g., 8GB RAM, 256GB storage)
- color_search: Phones in specific colors or asking about available colors
- comparison: Compare two or more phones
- recommendation: Which phone to buy, suggestions
- stock_check: Is phone available
- followup: Pronoun reference (that, it, အဲဒါ)
- unknown: Cannot determine

Return ONLY JSON:
{{
    "intent": "intent_name",
    "confidence": 0.0 to 1.0,
    "reason": "why this intent"
}}"""

    try:
        import json
        response = llm.invoke(prompt)
        content = response.content.strip()
        content = re.sub(r'```json\s*|\s*```', '', content)
        result = json.loads(content)

        intent_str = result.get('intent', 'unknown')
        confidence = result.get('confidence', 0.5)

        # Convert string to Intent enum
        try:
            intent = Intent(intent_str)
        except ValueError:
            intent = Intent.UNKNOWN

        return intent, confidence

    except Exception as e:
        logger.error(f"LLM intent classification error: {e}")
        return Intent.UNKNOWN, 0.0


# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def is_database_intent(intent: Intent) -> bool:
    """Check if intent requires database access"""
    db_intents = {
        Intent.BRAND_LIST,
        Intent.MODEL_LIST,
        Intent.PRICE_FILTER,
        Intent.SPEC_SEARCH,
        Intent.RAM_STORAGE_SEARCH,
        Intent.COLOR_SEARCH,
        Intent.COMPARISON,
        Intent.RECOMMENDATION,
        Intent.STOCK_CHECK,
    }
    return intent in db_intents


def is_policy_intent(intent: Intent) -> bool:
    """Check if intent requires shop policy knowledge"""
    return intent == Intent.CRM_QUESTION


def is_technical_support_intent(intent: Intent) -> bool:
    """Check if intent is technical support (can use LLM general knowledge)"""
    return intent == Intent.TECHNICAL_SUPPORT


# ═══════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Initialize classifier
    classifier = HybridIntentClassifier()

    # Test queries
    test_queries = [
        # CRM - Different ways to ask
        "ဖုန်းနံပါတ် ဘယ်လောက်လဲ?",
        "ဆိုင် ဘယ်မှာလဲ?",

        # Technical Support
        "ဖုန်း wifi မတက်ဘူး",
        "how to transfer data to new phone",

        # Products
        "8GB RAM နဲ့ ဘာတွေရှိလဲ?",
        "256GB storage ဖုန်းတွေ",
        "black color ရှိလား?",
        "camera အရမ်းကောင်းတဲ့ ဖုန်း",
    ]

    print("Testing Hybrid Intent Classifier:\n")

    for query in test_queries:
        intent, confidence = classifier.classify(query)
        print(f"Query: {query}")
        print(f"→ Intent: {intent.value} (confidence: {confidence:.2f})")
        print(f"→ DB needed: {is_database_intent(intent)}")
        print(f"→ Policy needed: {is_policy_intent(intent)}")
        print(f"→ Tech support: {is_technical_support_intent(intent)}")
        print("-" * 60)

    print("\nClassification Stats:")
    print(classifier.get_stats())