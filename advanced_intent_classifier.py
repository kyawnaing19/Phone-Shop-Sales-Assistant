"""
╔══════════════════════════════════════════════════════════════════════════╗
║              ADVANCED INTENT CLASSIFICATION SYSTEM                       ║
║              Hybrid Approach: Rules + Embeddings + LLM                   ║
║                                                                          ║
║  SOLVES: Missing keyword problems                                        ║
║  METHOD: Multi-strategy with fallback                                    ║
║                                                                          ║
║  Strategy 1: Comprehensive Rule-based (Fast)                             ║
║  Strategy 2: Semantic Similarity (Fuzzy)                                 ║
║  Strategy 3: LLM Classification (Accurate)                               ║
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
    # No DB needed
    GREETING = "greeting"
    CASUAL = "casual"
    CRM_QUESTION = "crm_question"

    # DB needed
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
                r'(အချိန်|ချိန်)',

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
                r'(information|data|details)',

                # General CRM
                r'(crm|customer.*relationship)',
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
                r'(\d+|သိန်း|lakh).*(သိန်း|lakh).*(အောက်|under|below|less)',
                r'(under|below|အောက်|မကျော်).*(သိန်း|lakh|\d+)',
                r'(budget|ဘတ်ဂျက်|ငွေ).*(သိန်း|\d+)',
                r'(သိန်း|\d+).*(နဲ့|ဖြင့်).*(ဝယ်|ရ)',
                r'(cheap|affordable|သက်သာ|စျေးသက်သာ)',
                r'(price.*range|ဈေး.*အကြား)',
            ],

            Intent.SPEC_SEARCH: [
                r'(camera|ကင်မရာ).*(good|best|ကောင်း|အကောင်းဆုံး)',
                r'(battery|ဘက်ထရီ).*(long|good|ကြာ|ကောင်း)',
                r'(gaming|game|ဂိမ်း)',
                r'(5g|4g|network)',
                r'(fast.*charg|quick.*charg)',
                r'(display|screen|မျက်နှာပြင်)',
                r'(ram|rom|storage|memory)',
            ],

            Intent.COMPARISON: [
                r'(compare|comparison|ယှဉ်)',
                r'(vs|versus|နဲ့)',
                r'(difference|differ|ခြား)',
                r'(better|best|ပိုကောင်း).*(than|or)',
                r'(which.*better|ဘယ်ဟာ.*ပိုကောင်း)',
            ],

            Intent.RECOMMENDATION: [
                r'(recommend|suggest|advise|အကြံပြု)',
                r'(which.*(should|phone|buy)|ဘယ်.*ဖုန်း)',
                r'(best|အကောင်းဆုံး)',
                r'(good.*phone|phone.*good)',
                r'(help.*choose|ရွေး.*ပေး)',
            ],

            Intent.STOCK_CHECK: [
                r'(have|got).*(stock|available|ရှိ)',
                r'(available|in.*stock|ရနိုင်|ရှိလား)',
                r'(do.*have|can.*get)',
                r'(stock|လက်ကျန်|ပမာဏ)',
            ],

            Intent.FOLLOWUP: [
                r'^(that|this|those|these|it)(\s|$)',
                r'^(အဲဒါ|ဒါ|သူ|ဟို)(\s|$)',
                r'^(ဈေး|price|battery|camera|spec)s?\??$',
                r'^(how.*much|ဘယ်လောက်)\??$',
            ],
        }

    def classify(self, message: str, has_history: bool = False) -> Tuple[Intent, float]:
        """
        Classify using comprehensive patterns
        Returns: (intent, confidence_score)
        """
        msg_lower = message.lower().strip()

        # Check each intent's patterns
        for intent, patterns in self.patterns.items():
            # Skip FOLLOWUP if no history
            if intent == Intent.FOLLOWUP and not has_history:
                continue

            for i, pattern in enumerate(patterns):
                if re.search(pattern, msg_lower, re.IGNORECASE):
                    # Confidence based on pattern specificity
                    # More specific patterns (later in list) = higher confidence
                    confidence = 0.7 + (i / len(patterns)) * 0.3
                    logger.info(f"🎯 Rule Match: {intent.value} (conf={confidence:.2f})")
                    return intent, confidence

        # No pattern matched
        return Intent.UNKNOWN, 0.0


# ═══════════════════════════════════════════════════════════════════════════
# SEMANTIC SIMILARITY CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════

class SemanticClassifier:
    """
    Use semantic similarity to catch queries with missing keywords
    Uses simple word overlap and fuzzy matching
    """

    def __init__(self):
        self.intent_keywords = self._build_keyword_sets()

    def _build_keyword_sets(self) -> Dict[Intent, set]:
        """Build comprehensive keyword sets for each intent"""
        return {
            Intent.CRM_QUESTION: {
                # English
                'phone', 'number', 'contact', 'call', 'reach', 'address', 'location',
                'where', 'shop', 'store', 'hour', 'time', 'open', 'close', 'warranty',
                'guarantee', 'return', 'refund', 'exchange', 'payment', 'pay', 'method',
                'support', 'help', 'service', 'privacy', 'data', 'security',
                # Myanmar
                'ဖုန်း', 'နံပါတ်', 'ဆက်သွယ်', 'လိပ်စာ', 'ဆိုင်', 'နေရာ', 'ဘယ်မှာ',
                'အချိန်', 'ဖွင့်', 'ပိတ်', 'အာမခံ', 'ပြန်အမ်း', 'ငွေ', 'ကူညီ',
            },

            Intent.BRAND_LIST: {
                'brand', 'brands', 'phone', 'phones', 'available', 'have', 'show',
                'list', 'all', 'ဖုန်း', 'ရှိ', 'ပြ', 'အားလုံး', 'ဘာတွေ',
            },

            Intent.PRICE_FILTER: {
                'price', 'budget', 'cheap', 'under', 'below', 'lakh', 'affordable',
                'ဈေး', 'ဘတ်ဂျက်', 'သိန်း', 'အောက်', 'သက်သာ',
            },

            Intent.SPEC_SEARCH: {
                'camera', 'battery', 'gaming', 'game', 'display', 'screen', '5g',
                'ram', 'storage', 'fast', 'charging',
                'ကင်မရာ', 'ဘက်ထရီ', 'ဂိမ်း', 'မျက်နှာပြင်',
            },

            Intent.COMPARISON: {
                'compare', 'comparison', 'vs', 'versus', 'difference', 'better',
                'ယှဉ်', 'နဲ့', 'ခြား', 'ပိုကောင်း',
            },

            Intent.RECOMMENDATION: {
                'recommend', 'suggest', 'which', 'should', 'buy', 'best', 'choose',
                'အကြံပြု', 'ဘယ်', 'ဝယ်', 'အကောင်းဆုံး', 'ရွေး',
            },
        }

    def classify(self, message: str) -> Tuple[Intent, float]:
        """
        Classify using keyword overlap
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
- crm_question: Phone number, address, hours, warranty, payment, support
- brand_list: What phones/brands available
- model_list: Show models of a specific brand
- price_filter: Phones within price range
- spec_search: Phones with specific features (camera, battery, gaming)
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
# USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Initialize classifier
    classifier = HybridIntentClassifier()

    # Test queries
    test_queries = [
        # CRM - Different ways to ask
        "ဖုန်းနံပါတ် ဘယ်လောက်လဲ?",  # Direct
        "ဆက်သွယ်ချင်တယ်",  # No "number" keyword
        "ဘယ်လိုခေါ်ရမလဲ",  # Indirect
        "ဆိုင် ဘယ်မှာလဲ?",  # Address
        "နေရာ ပြောပေးပါ",  # Location

        # Products - Different phrasings
        "ဖုန်း ဘယ်လိုမျိုးတွေ ရှိလဲ?",  # Brand list
        "Samsung ဘာတွေ ရရှိနိုင်လဲ?",  # Model list
        "ငါးသိန်းနဲ့ ဝယ်လို့ရမလား?",  # Price filter
        "ကင်မရာ အရမ်းကောင်းတဲ့ ဖုန်း",  # Spec search
    ]

    print("Testing Hybrid Intent Classifier:\n")

    for query in test_queries:
        intent, confidence = classifier.classify(query)
        print(f"Query: {query}")
        print(f"→ Intent: {intent.value} (confidence: {confidence:.2f})")
        print("-" * 60)

    print("\nClassification Stats:")
    print(classifier.get_stats())