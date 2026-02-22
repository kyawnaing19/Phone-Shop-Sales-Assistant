"""
╔══════════════════════════════════════════════════════════════════════════╗
║              ADVANCED INTENT CLASSIFICATION SYSTEM - v3.0                ║
║              Enhanced for RAM/Storage & Color queries                    ║
║              Hybrid Approach: Rules + Semantic + LLM                     ║
║                                                                          ║
║  v3.0 FIXES:                                                             ║
║  ✓ FIX #1: Multi-intent support (returns List instead of single)       ║
║  ✓ FIX #2: Rule classifier collects ALL matches (no early return)      ║
║  ✓ FIX #3: Pattern conflicts resolved (ပျက်, ကူညီ, ရှိလား)             ║
║  ✓ FIX #4: Semantic classifier uses weighted scoring (not naive count) ║
║  ✓ FIX #5: ORDER_INPUT now has patterns + state-based detection        ║
║  ✓ FIX #6: FOLLOWUP pattern tightened (requires short msg or pronoun)  ║
║  ✓ FIX #7: Confidence scoring based on match specificity, not length   ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# INTENT DEFINITIONS WITH EXAMPLE QUERIES
# ═══════════════════════════════════════════════════════════════════════════

class Intent(str, Enum):
    """Intent types with detailed descriptions"""
    # No DB needed - Non-sales queries
    GREETING         = "greeting"
    CASUAL           = "casual"
    CRM_QUESTION     = "crm_question"
    TECHNICAL_SUPPORT = "technical_support"

    # DB needed - Sales & Product queries
    BRAND_LIST        = "brand_list"
    MODEL_LIST        = "model_list"
    PRICE_FILTER      = "price_filter"
    SPEC_SEARCH       = "spec_search"
    RAM_STORAGE_SEARCH = "ram_storage_search"
    COLOR_SEARCH      = "color_search"
    COMPARISON        = "comparison"
    RECOMMENDATION    = "recommendation"
    STOCK_CHECK       = "stock_check"

    # Ordering intents
    BUY_PRODUCT  = "buy_product"
    CART_COMMAND = "cart_command"
    ORDER_INPUT  = "order_input"

    # Follow-up
    FOLLOWUP = "followup"
    UNKNOWN  = "unknown"


# ───────────────────────────────────────────────────────────────────────────
# FIX #7: Each intent has a BASE confidence score based on specificity.
# High = very specific keywords unlikely to appear in other intents.
# Medium = moderate specificity.
# Low = broad / common words that may overlap.
# ───────────────────────────────────────────────────────────────────────────
INTENT_BASE_CONFIDENCE: Dict[Intent, float] = {
    Intent.GREETING:          0.95,  # Very distinctive keywords
    Intent.CASUAL:            0.85,
    Intent.CRM_QUESTION:      0.80,
    Intent.TECHNICAL_SUPPORT: 0.85,
    Intent.BRAND_LIST:        0.80,
    Intent.MODEL_LIST:        0.88,  # Brand names are very specific
    Intent.PRICE_FILTER:      0.90,  # Price patterns are very specific
    Intent.SPEC_SEARCH:       0.82,
    Intent.RAM_STORAGE_SEARCH:0.92,  # GB + RAM/ROM very specific
    Intent.COLOR_SEARCH:      0.88,
    Intent.COMPARISON:        0.90,
    Intent.RECOMMENDATION:    0.83,
    Intent.STOCK_CHECK:       0.75,  # "ရှိလား" is common, lower base
    Intent.BUY_PRODUCT:       0.90,
    Intent.CART_COMMAND:      0.92,
    Intent.ORDER_INPUT:       0.88,
    Intent.FOLLOWUP:          0.70,  # Broad patterns, lower base
    Intent.UNKNOWN:           0.00,
}


# Training examples for each intent (for semantic matching)
INTENT_EXAMPLES = {
    Intent.GREETING: [
        "hello", "hi", "hey", "good morning", "good afternoon",
        "မင်္ဂလာပါ", "မင်္ဂလာ", "ဟယ်လို", "ဟိုင်း",
    ],

    Intent.CASUAL: [
        "how are you", "what's up", "thank you", "thanks", "ok", "okay",
        "bye", "see you", "ကျေးဇူး", "အိုကေ", "ရပြီ", "ဟုတ်ကဲ့",
    ],

    Intent.CRM_QUESTION: [
        "contact number", "shop address", "shop location",
        "opening hours", "closing time", "warranty policy", "return policy", "refund",
        "payment method", "installment plan", "customer service",
        "ဖုန်းနံပါတ်", "ဆက်သွယ်ရန်", "လိပ်စာ", "ဆိုင်လိပ်စာ",
        "ဆိုင်ဖွင့်ချိန်", "ပိတ်ချိန်", "အာမခံ", "ပြန်အမ်း", "ငွေပေးချေမှု",
        "အရစ်ကျ", "ဝန်ဆောင်မှု",
    ],

    Intent.TECHNICAL_SUPPORT: [
        "how to use", "how to setup", "how to install", "how to transfer",
        "phone not working", "battery draining fast", "screen frozen", "wifi not connecting",
        "bluetooth issue", "camera not working", "app crashing", "software update",
        "factory reset", "backup restore",
        "ဘယ်လို အသုံးပြုရမလဲ", "ဖုန်း ဘယ်လို သုံးရမလဲ", "setting ပြင်နည်း",
        "transfer လုပ်နည်း", "backup လုပ်နည်း", "ဖုန်း မလုပ်ဘူး",
        "battery ကုန်မြန်", "screen မလုပ်", "wifi မတက်", "ဖုန်း ပြင်နည်း",
    ],

    Intent.BRAND_LIST: [
        "what brands do you have", "show all phones", "available phone brands",
        "which brands do you sell", "list all brands",
        "ဘယ် brand တွေရှိလဲ", "ဖုန်းတွေ ပြပါ", "ဖုန်း ဘာတွေရှိလဲ",
        "brand အားလုံး ပြပါ",
    ],

    Intent.MODEL_LIST: [
        "samsung phones available", "iphone models", "show me xiaomi phones",
        "oppo models list", "vivo phones",
        "samsung ဘာတွေရှိလဲ", "iphone မော်ဒယ်တွေ", "xiaomi ဖုန်းတွေ",
    ],

    Intent.PRICE_FILTER: [
        "phones under 5 lakh", "below 3 lakh budget", "phones under 500000",
        "budget 5 lakh", "between 3 and 7 lakh", "affordable phones",
        "5 သိန်းအောက်", "3 သိန်း အောက်", "ဈေးသက်သာတဲ့ ဖုန်း",
        "သိန်း 10 အောက်", "ဘတ်ဂျက် 5 သိန်း",
    ],

    Intent.SPEC_SEARCH: [
        "good camera phone", "long battery life", "gaming phone", "5G phone",
        "fast charging phone", "best processor phone",
        "camera ကောင်းတဲ့", "battery ကြာတဲ့", "ဂိမ်းဆော့ဖို့",
    ],

    Intent.RAM_STORAGE_SEARCH: [
        "8GB RAM phone", "256GB storage phone", "12GB RAM", "512GB internal storage",
        "RAM 8GB နဲ့ ဖုန်း", "256GB ရှိတဲ့ ဖုန်း", "memory ကြီးတဲ့ ဖုန်း",
        "ROM 256GB",
    ],

    Intent.COLOR_SEARCH: [
        "black color phone", "white phone available", "blue color phones",
        "available in gold", "what colors do you have",
        "နက်ရောင် ဖုန်း", "အဖြူရောင် ဖုန်း", "ဘယ်အရောင်ရှိလဲ",
    ],

    Intent.COMPARISON: [
        "compare iphone vs samsung", "difference between two phones", "which is better",
        "iphone vs samsung comparison", "ယှဉ်ကြည့်ချင်တယ်",
        "iphone နဲ့ samsung ယှဉ်", "ဘယ်ဟာပိုကောင်းလဲ",
    ],

    Intent.RECOMMENDATION: [
        "which phone should i buy", "recommend a phone for me", "best phone to buy",
        "suggest a phone for gaming", "what phone do you recommend",
        "ဘယ်ဖုန်း ဝယ်ရမလဲ", "အကြံပြုပါ", "ဘယ်ဟာ အကောင်းဆုံးလဲ", "ရွေးပေးပါ",
    ],

    Intent.STOCK_CHECK: [
        "is this phone in stock", "do you have iphone 15", "is samsung s24 available",
        "stock ရှိလား", "ဒီဖုန်း ရှိသေးလား", "လက်ကျန် ရှိသေးလား",
    ],

    Intent.BUY_PRODUCT: [
        "i want to buy this phone", "i'll take this one", "want to purchase",
        "order this phone", "how do i buy",
        "ဒီဖုန်း ဝယ်မယ်", "ဒါ ယူမယ်", "order တင်မယ်", "ဝယ်ချင်တယ်",
    ],

    Intent.CART_COMMAND: [
        "show my cart", "view cart", "checkout now", "add to cart",
        "add another one", "continue to checkout",
        "cart ကြည့်ချင်တယ်", "checkout လုပ်မယ်", "ထပ်ထည့်မယ်",
    ],

    # FIX #5: ORDER_INPUT now has real examples
    Intent.ORDER_INPUT: [
        "my address is", "deliver to", "my phone number is 09",
        "send to yangon", "township is", "name is",
        "လိပ်စာ ကတော့", "ပို့ပေးပါ", "ကျွန်တော့် နာမည်",
        "09 နဲ့ ဆက်သွယ်", "မြို့နယ် က", "တိုင်း က",
    ],

    Intent.FOLLOWUP: [
        "that one", "this one", "how much is it", "what about that",
        "အဲဒါ ဘယ်လောက်လဲ", "ဒါ ဘယ်လောက်လဲ", "အဲဒါရော",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# FIX #4 & #7: Intent-specific keyword weights for semantic scoring.
# Keywords listed here are "anchor" words — highly specific to that intent.
# Matching an anchor keyword boosts confidence significantly.
# ═══════════════════════════════════════════════════════════════════════════
ANCHOR_KEYWORDS: Dict[Intent, List[str]] = {
    Intent.GREETING:           ["hello", "hi", "hey", "မင်္ဂလာ", "ဟယ်လို"],
    Intent.CASUAL:             ["thanks", "thank", "ကျေးဇူး", "okay", "bye"],
    Intent.CRM_QUESTION:       ["warranty", "refund", "installment", "hotline", "အာမခံ", "အရစ်ကျ", "ငွေပြန်"],
    Intent.TECHNICAL_SUPPORT:  ["troubleshoot", "reset", "backup", "frozen", "crashed", "မလုပ်ဘူး", "ချို့ယွင်း"],
    Intent.BRAND_LIST:         ["brands", "brand"],
    Intent.MODEL_LIST:         ["samsung", "iphone", "xiaomi", "oppo", "vivo", "realme", "huawei", "မော်ဒယ်"],
    Intent.PRICE_FILTER:       ["lakh", "သိန်း", "budget", "ဘတ်ဂျက်", "affordable", "သက်သာ"],
    Intent.SPEC_SEARCH:        ["camera", "battery", "gaming", "processor", "5g", "charging", "ကင်မရာ", "ဘက်ထရီ"],
    Intent.RAM_STORAGE_SEARCH: ["ram", "rom", "storage", "memory", "gb", "tb", "ရမ်", "ဂျီဘီ"],
    Intent.COLOR_SEARCH:       ["color", "colour", "black", "white", "blue", "gold", "silver", "pink",
                                 "အရောင်", "နက်", "အဖြူ", "အပြာ", "ရွှေ"],
    Intent.COMPARISON:         ["vs", "versus", "compare", "difference", "better", "ယှဉ်", "ခြားနားချက်"],
    Intent.RECOMMENDATION:     ["recommend", "suggest", "best", "advice", "အကြံပြု", "ရွေးပေး", "အကောင်းဆုံး"],
    Intent.STOCK_CHECK:        ["stock", "available", "in stock", "လက်ကျန်"],
    Intent.BUY_PRODUCT:        ["buy", "purchase", "order", "ဝယ်", "ယူ", "အော်ဒါ"],
    Intent.CART_COMMAND:       ["cart", "checkout", "တောင်း", "ထည့်"],
    Intent.ORDER_INPUT:        ["address", "deliver", "township", "လိပ်စာ", "ပို့", "မြို့နယ်", "တိုင်း"],
    Intent.FOLLOWUP:           ["that", "this", "those", "it", "အဲဒါ", "ဒါ"],
}


# ═══════════════════════════════════════════════════════════════════════════
# FIX #3: Intents that are MUTUALLY EXCLUSIVE (only highest wins).
# If both match in the same message, the one with higher confidence wins.
# ═══════════════════════════════════════════════════════════════════════════
EXCLUSIVE_INTENT_GROUPS: List[List[Intent]] = [
    # Social intents — can't be greeting AND casual at same time
    [Intent.GREETING, Intent.CASUAL],
    # Technical phone help vs shop policy — distinct contexts
    [Intent.TECHNICAL_SUPPORT, Intent.CRM_QUESTION],
    # Ordering flow is mutually exclusive
    [Intent.BUY_PRODUCT, Intent.CART_COMMAND, Intent.ORDER_INPUT],
]


# ═══════════════════════════════════════════════════════════════════════════
# RULE-BASED CLASSIFIER  (FIX #2, #3, #6, #7)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PatternRule:
    """
    A single pattern rule with metadata.
    FIX #7: confidence is set explicitly per pattern, not derived from length.
    """
    pattern: str
    confidence: float = 0.85  # Default confidence
    # FIX #6: If True, pattern only fires when message is short (<=5 words)
    requires_short_message: bool = False


class RuleBasedClassifier:
    """
    FIX #2: Collects ALL matching intents instead of returning on first match.
    FIX #3: Resolves conflicts using mutual exclusion groups.
    FIX #6: FOLLOWUP patterns tightened with requires_short_message flag.
    FIX #7: Each pattern has an explicit confidence score.
    """

    def __init__(self):
        self.rules: Dict[Intent, List[PatternRule]] = self._build_rules()

    def _build_rules(self) -> Dict[Intent, List[PatternRule]]:
        return {

            # ── GREETING ──────────────────────────────────────────────────
            Intent.GREETING: [
                PatternRule(r'^(hi|hello|hey|hola|greetings)(\s|!|\.|$)', confidence=0.97),
                PatternRule(r'^(good\s+(morning|afternoon|evening|night))',  confidence=0.97),
                PatternRule(r'^မင်္ဂလာ',                                     confidence=0.97),
                PatternRule(r'^ဟယ်လို',                                      confidence=0.97),
                PatternRule(r'^ဟိုင်း',                                       confidence=0.95),
            ],

            # ── CASUAL ────────────────────────────────────────────────────
            Intent.CASUAL: [
                PatternRule(r'(how\s+are\s+you|how.*doing)',                  confidence=0.90),
                PatternRule(r'\b(thank\s+you|thanks|thx|appreciate)\b',       confidence=0.93),
                PatternRule(r'^(ok|okay|sure|fine|alright|got\s+it)(\s|!|\.|$)', confidence=0.90),
                PatternRule(r'ကျေးဇူး',                                       confidence=0.93),
                PatternRule(r'^(အိုကေ|ရပြီ|ဟုတ်ကဲ့)(\s|$)',                  confidence=0.90),
                PatternRule(r'\b(bye|goodbye|see\s+you)\b',                   confidence=0.90),
            ],

            # ── CRM_QUESTION ──────────────────────────────────────────────
            # FIX #3: Removed generic "problem/help" patterns that conflicted
            # with TECHNICAL_SUPPORT. Now CRM only covers shop policy topics.
            Intent.CRM_QUESTION: [
                # Contact
                PatternRule(r'(contact|hotline|customer.*line)\s*(number|info|details)?', confidence=0.90),
                PatternRule(r'(ဖုန်း|မိုဘိုင်း)\s*(နံပါတ်|နံပတ်)',           confidence=0.90),
                PatternRule(r'(ဆက်သွယ်|ခေါ်ဆို)\s*(ရန်|နံပါတ်)',             confidence=0.90),
                # Address/Location
                PatternRule(r'(shop|store|branch)\s*(address|location|where)', confidence=0.88),
                PatternRule(r'where\s+(is|are)\s+(the\s+)?(shop|store|branch)', confidence=0.88),
                PatternRule(r'(ဆိုင်|စတိုး)\s*(လိပ်စာ|နေရာ|ဘယ်မှာ)',         confidence=0.88),
                PatternRule(r'\b(လိပ်စာ)\b',                                  confidence=0.82),
                PatternRule(r'\b(map|မြေပုံ)\b',                              confidence=0.80),
                # Hours
                PatternRule(r'(opening|closing|business)\s*(hour|time)',       confidence=0.88),
                PatternRule(r'(open|close)\s*(time|hour|at)',                  confidence=0.86),
                PatternRule(r'(ဆိုင်)\s*(ဖွင့်|ပိတ်|အချိန်)',                 confidence=0.88),
                # Warranty/Repair Policy (shop policy, not how-to-fix)
                PatternRule(r'\b(warranty|guarantee|အာမခံ)\b',                 confidence=0.88),
                PatternRule(r'warranty\s*(period|cover|duration)',             confidence=0.90),
                # Return/Refund
                PatternRule(r'\b(return|refund|exchange|ပြန်အမ်း|လဲလှယ်)\b',  confidence=0.88),
                PatternRule(r'(money\s+back|get.*refund)',                     confidence=0.90),
                # Payment
                PatternRule(r'(payment|pay)\s*(method|way|option)',            confidence=0.88),
                PatternRule(r'\b(kbz|wave|cb\s*pay|mobile\s*banking)\b',       confidence=0.85),
                PatternRule(r'\b(installment|အရစ်ကျ|လစဉ်)\b',                 confidence=0.90),
                PatternRule(r'\b(invoice|receipt|ဘောင်ချာ)\b',                 confidence=0.85),
                # Privacy/Policy
                PatternRule(r'\b(privacy|data\s*policy|personal\s*data)\b',    confidence=0.82),
            ],

            # ── TECHNICAL_SUPPORT ─────────────────────────────────────────
            # FIX #3: "ပျက်" (broken/damaged) moved here from CRM.
            # "ပြင်" with "ဘယ်လို/နည်း" = how to fix (tech support).
            # "ပြင်" alone = repair service (CRM). Handled by specificity.
            Intent.TECHNICAL_SUPPORT: [
                # How-to
                PatternRule(r'(how\s+to|ဘယ်လို)\s*(use|setup|install|config|သုံး|သတ်မှတ်)', confidence=0.90),
                PatternRule(r'(how\s+do\s+i)\s*(transfer|backup|restore|sync)',               confidence=0.90),
                PatternRule(r'(setting|ဆက်တင်)\s*(change|ပြင်|adjust)\s*(နည်း|လုပ်နည်း)?',   confidence=0.88),
                PatternRule(r'(transfer|backup|restore|sync)\s*(လုပ်နည်း|နည်း)',             confidence=0.90),
                PatternRule(r'(screenshot|screen\s*record)\s*(လုပ်နည်း|how)',                confidence=0.88),
                # Troubleshooting — device malfunction
                PatternRule(r'(phone|ဖုန်း)\s*(not\s+working|မလုပ်|ပျက်)',                   confidence=0.90),
                PatternRule(r'(battery|ဘက်ထရီ)\s*(drain|fast|ကုန်မြန်|သုံးပြီး|ကုန်)',       confidence=0.90),
                PatternRule(r'(screen|မျက်နှာပြင်)\s*(frozen|black|stuck|မလုပ်|ပိတ်)',       confidence=0.90),
                # FIX #3: wifi/bluetooth problems = tech support, not CRM
                PatternRule(r'(wifi|ဝိုင်ဖိုင်)\s*(not\s*connect|problem|မတက်|မဆက်)',        confidence=0.92),
                PatternRule(r'(bluetooth|ဘလူးတုသ်)\s*(not\s*work|issue|မတက်)',               confidence=0.92),
                PatternRule(r'(app|အက်ပ်)\s*(crash|close|freeze|ပိတ်|မလုပ်)',                confidence=0.90),
                PatternRule(r'(camera|ကင်မရာ)\s*(not\s+work|blurry|မရှင်း|မလုပ်)',           confidence=0.90),
                # Software
                PatternRule(r'(update|အပ်ဒိတ်)\s*(software|system|phone|os)',                confidence=0.88),
                PatternRule(r'\b(factory\s+reset|hard\s+reset|ပြန်လည်သတ်မှတ်)\b',            confidence=0.92),
            ],

            # ── BRAND_LIST ────────────────────────────────────────────────
            Intent.BRAND_LIST: [
                PatternRule(r'(what|which)\s*(brand|phone|model)\s*(do\s+you\s+have|available|sell)', confidence=0.90),
                PatternRule(r'(show|list|display)\s*(all|every)\s*(phone|brand|model)',               confidence=0.90),
                PatternRule(r'(available|ရှိတဲ့)\s*(brand|phone)\s*(တွေ|များ)?',                      confidence=0.85),
                PatternRule(r'(ဘယ်|ဘာ)\s*(brand|ဖုန်း)\s*(တွေ|များ)\s*(ရှိ|လဲ)',                     confidence=0.88),
                PatternRule(r'(ဖုန်း|phone)\s*(အားလုံး|all)\s*(ပြ|show)',                             confidence=0.88),
                PatternRule(r'ဖုန်းတွေ\s*ပြပါ',                                                      confidence=0.90),
            ],

            # ── MODEL_LIST ────────────────────────────────────────────────
            Intent.MODEL_LIST: [
                PatternRule(r'\b(samsung|iphone|xiaomi|oppo|vivo|realme|huawei|pixel|oneplus)\b\s*(phone|model|မော်ဒယ်|ဖုန်း)', confidence=0.92),
                PatternRule(r'(show|ပြ)\s*(me\s+)?(samsung|iphone|xiaomi|oppo|vivo|realme)',                                      confidence=0.90),
                PatternRule(r'\b(samsung|iphone|xiaomi|oppo|vivo)\b\s*(ဘာတွေ|တွေ|များ)',                                          confidence=0.88),
                # Brand name anywhere in the message (mixed EN+Burmese sentences)
                PatternRule(r'\b(samsung|iphone|xiaomi|oppo|vivo|realme|huawei|pixel|oneplus)\b',                                  confidence=0.85),
            ],

            # ── PRICE_FILTER ──────────────────────────────────────────────
            Intent.PRICE_FILTER: [
                PatternRule(r'(under|below|less\s+than|within)\s*\d*\s*(lakh|သိန်း|k|kyat|ကျပ်)',   confidence=0.93),
                PatternRule(r'\d+\s*(lakh|သိန်း)\s*(under|below|အောက်|ကျပ်)',                       confidence=0.93),
                PatternRule(r'(budget|ဘတ်ဂျက်)\s*(is|of|ကတော့)?\s*\d+\s*(lakh|သိန်း)?',            confidence=0.90),
                PatternRule(r'(between|နဲ့\s*ကြား)\s*\d+\s*(and|နဲ့)\s*\d+\s*(lakh|သိန်း)',         confidence=0.93),
                PatternRule(r'\d+\s*သိန်း\s*(အောက်|ကျော်|နဲ့)',                                     confidence=0.92),
                PatternRule(r'\b(cheap|affordable|သက်သာ|ဈေးသက်သာ)\b',                              confidence=0.82),
            ],

            # ── SPEC_SEARCH ───────────────────────────────────────────────
            Intent.SPEC_SEARCH: [
                PatternRule(r'(camera|ကင်မရာ)\s*(good|best|ကောင်း|excellent|အကောင်းဆုံး)',   confidence=0.88),
                PatternRule(r'(battery|ဘက်ထရီ)\s*(long|last|good|ကြာ|ကောင်း)',              confidence=0.88),
                PatternRule(r'(gaming|ဂိမ်း)\s*(phone|ဖုန်း)',                               confidence=0.90),
                PatternRule(r'\b(5g|4g)\s*(phone|support|network|compatible)',               confidence=0.88),
                PatternRule(r'(fast\s+charg|quick\s+charg|မြန်တဲ့\s*အားသွင်း)',             confidence=0.88),
                PatternRule(r'\b(processor|chip|snapdragon|dimensity|helio)\b',              confidence=0.88),
                PatternRule(r'(performance|speed|မြန်)',                                      confidence=0.80),
            ],

            # ── RAM_STORAGE_SEARCH ────────────────────────────────────────
            Intent.RAM_STORAGE_SEARCH: [
                PatternRule(r'\b(\d+)\s*gb\s*(ram|ရမ်)\b',                              confidence=0.95),
                PatternRule(r'\b(ram|ရမ်|memory)\s*(\d+)\s*gb\b',                        confidence=0.95),
                PatternRule(r'\b(\d+)\s*gb\s*(storage|rom|ရုမ်|internal)\b',             confidence=0.95),
                PatternRule(r'\b(storage|rom|internal)\s*(\d+)\s*gb\b',                  confidence=0.95),
                PatternRule(r'\b(\d+)\s*gb\b.*\b(\d+)\s*gb\b',                           confidence=0.92),  # e.g., "8GB 256GB"
                PatternRule(r'\b(\d+)\s*tb\s*(storage|rom|internal)\b',                  confidence=0.95),
                PatternRule(r'(memory|သိုလှောင်မှု)\s*(ကြီး|large|many|များ)',           confidence=0.82),
            ],

            # ── COLOR_SEARCH ──────────────────────────────────────────────
            Intent.COLOR_SEARCH: [
                PatternRule(r'\b(black|white|blue|red|green|gold|silver|pink|purple|grey|gray)\b\s*(phone|color|ဖုန်း|available)?', confidence=0.88),
                PatternRule(r'(phone|model|ဖုန်း)\s*(come|available|ရ)\s*(in\s+)?(color|colour|အရောင်)',                            confidence=0.88),
                PatternRule(r'(available|ရှိ|ဘာ)\s*(color|colour|အရောင်)\s*(option|တွေ|ရှိ|လဲ)?',                                    confidence=0.88),
                PatternRule(r'(နက်|အဖြူ|အပြာ|အနီ|အစိမ်း|ရွှေ|ငွေ|ပန်း|ခရမ်း)\s*(ရောင်)',                                           confidence=0.90),
                PatternRule(r'ဘယ်အရောင်\s*(ရှိ|ရ)',                                                                                   confidence=0.90),
            ],

            # ── COMPARISON ────────────────────────────────────────────────
            Intent.COMPARISON: [
                PatternRule(r'(compare|comparison)\s*(between)?\s*\w+\s*(and|vs|versus)\s*\w+', confidence=0.93),
                PatternRule(r'\b(vs|versus)\b',                                                  confidence=0.90),
                PatternRule(r'(difference|differ)\s*(between)',                                   confidence=0.90),
                PatternRule(r'(iphone|samsung|xiaomi|oppo|vivo)\s*(vs|နဲ့|and)\s*(iphone|samsung|xiaomi|oppo|vivo)', confidence=0.95),
                PatternRule(r'\bယှဉ်ကြည့်\b',                                                   confidence=0.93),
                PatternRule(r'(ဘယ်ဟာ|ဘယ်တာ)\s*(ပိုကောင်း|better)',                              confidence=0.88),
            ],

            # ── RECOMMENDATION ────────────────────────────────────────────
            Intent.RECOMMENDATION: [
                PatternRule(r'(which|what)\s*(phone)?\s*(should\s+i|do\s+you)\s*(buy|recommend|suggest|pick)', confidence=0.90),
                PatternRule(r'\b(recommend|suggest|advice|advise)\b',                                           confidence=0.88),
                PatternRule(r'(best|top)\s*(phone|choice|option)\s*(for)',                                      confidence=0.88),
                PatternRule(r'(recommend|suggest|advice|အကြံပြု|ရွေးပေး|ရွေးချယ်ပေး)',                         confidence=0.88),
                PatternRule(r'(ဘယ်ဖုန်း)\s*(ဝယ်ရ|ကိုင်ရ|ယူရ)',                                               confidence=0.88),
                PatternRule(r'\b(အကောင်းဆုံး|best)\b',                                                         confidence=0.80),
            ],

            # ── STOCK_CHECK ───────────────────────────────────────────────
            # FIX #3: "ရှိလား" alone is low confidence (too common).
            # Specific model name + availability = high confidence.
            Intent.STOCK_CHECK: [
                PatternRule(r'(do\s+you\s+have|got)\s*(the\s+)?\w+',                               confidence=0.85),
                PatternRule(r'(is\s+)?(iphone|samsung|xiaomi|oppo|vivo|realme).*\s*(in\s+stock|available|ရှိ)', confidence=0.90),
                PatternRule(r'\b(in\s+stock|stock\s+ရှိ|လက်ကျန်)\b',                               confidence=0.88),
                PatternRule(r'(ဒီဖုန်း|model\s+\w+)\s*(ရှိ|ရ)\s*(သေး)?လား',                        confidence=0.85),
                # "ရှိလား" alone = low confidence, only fire if short message
                PatternRule(r'^(ရှိ|ရ)\s*လား\s*$', confidence=0.70, requires_short_message=True),
            ],

            # ── BUY_PRODUCT ───────────────────────────────────────────────
            Intent.BUY_PRODUCT: [
                PatternRule(r'(want|wanna|like)\s+to\s+(buy|purchase|order|get)',   confidence=0.92),
                PatternRule(r'(buy|purchase|order)\s+(this|that|the\s+\w+)',        confidence=0.92),
                PatternRule(r"(i'?ll|i\s+will)\s+(take|buy|get)",                  confidence=0.92),
                PatternRule(r'how\s+(do\s+i|to)\s+(buy|order|purchase)',            confidence=0.90),
                PatternRule(r'(ဒါ|အဲဒါ|ဒီဖုန်း)\s*(ဝယ်|ယူ)\s*(မယ်|ချင်)',         confidence=0.92),
                PatternRule(r'(order|အော်ဒါ)\s*(တင်|လုပ်)\s*(မယ်|ချင်)',           confidence=0.92),
                PatternRule(r'\bဝယ်ချင်တယ်\b',                                    confidence=0.90),
            ],

            # ── CART_COMMAND ──────────────────────────────────────────────
            Intent.CART_COMMAND: [
                PatternRule(r'\badd\s+to\s+cart\b',                                confidence=0.95),
                PatternRule(r'(view|show|check|open)\s*(my\s+)?cart',              confidence=0.93),
                PatternRule(r'\b(checkout|check\s+out)\b',                          confidence=0.93),
                PatternRule(r'\bcart\b',                                            confidence=0.88),
                PatternRule(r'(ဆက်|ထပ်)\s*(ထည့်|ယူ)',                             confidence=0.88),
                PatternRule(r'\bcart\s*ကြည့်\b',                                   confidence=0.92),
                PatternRule(r'\bcheckout\s*(လုပ်|မယ်)\b',                          confidence=0.93),
            ],

            # ── ORDER_INPUT ───────────────────────────────────────────────
            # FIX #5: Now has real patterns for delivery info detection
            Intent.ORDER_INPUT: [
                PatternRule(r'(my\s+)?(address\s+is|address\s*:)',                  confidence=0.92),
                PatternRule(r'(deliver|send|ship)\s*(to|me)\s+\w+',                confidence=0.90),
                PatternRule(r'(my\s+)?(phone\s*number\s+is|number\s+is)\s*0?9',    confidence=0.92),
                PatternRule(r'\b(township|ward|street|village|state|region|တိုင်း|မြို့နယ်|ရပ်ကွက်)\b', confidence=0.85),
                PatternRule(r'(နာမည်|name)\s*(က|is|ကတော့)\s*\w+',                 confidence=0.88),
                PatternRule(r'(လိပ်စာ)\s*(ကတော့|က|is)\s*\S+',                     confidence=0.90),
                PatternRule(r'(ပို့|deliver)\s*(ပေး|to)\s*(ပါ|\w+)',               confidence=0.88),
                PatternRule(r'\b09\d{7,9}\b',                                       confidence=0.88),  # Myanmar phone number
            ],

            # ── FOLLOWUP ──────────────────────────────────────────────────
            # FIX #6: Patterns are now tighter — require short messages OR
            # clear pronoun reference. Long messages with "this" won't fire.
            Intent.FOLLOWUP: [
                PatternRule(r'^(that\s+one|this\s+one|those|these)(\s*\??)?$',      confidence=0.85, requires_short_message=True),
                PatternRule(r'^(how\s+much|ဘယ်လောက်)(\s*\??)?$',                   confidence=0.82, requires_short_message=True),
                PatternRule(r'^(what\s+about\s+(it|that|this))(\s*\??)?$',          confidence=0.82, requires_short_message=True),
                PatternRule(r'^(the\s+)?(price|ဈေး|spec|detail)(\s*\??)?$',         confidence=0.80, requires_short_message=True),
                PatternRule(r'^(အဲဒါ|ဒါ|ဟို)\s*(ရော|ဘယ်လောက်|ဈေးဘယ်လောက်)(\s*\??)?$', confidence=0.85),
                PatternRule(r'\bအဲဒါရော\b',                                         confidence=0.85, requires_short_message=True),
            ],
        }

    def classify_multi(
        self,
        message: str,
        has_history: bool = False
    ) -> List[Tuple[Intent, float]]:
        """
        FIX #2: Collect ALL matching intents. Never returns on first match.
        FIX #3: Apply mutual exclusion resolution.
        FIX #6: Respect requires_short_message flag.
        FIX #7: Use per-pattern confidence scores.

        Returns: sorted list of (Intent, confidence) tuples, highest first.
        """
        msg_lower  = message.lower().strip()
        word_count = len(msg_lower.split())
        results: Dict[Intent, float] = {}

        for intent, rules in self.rules.items():
            for rule in rules:
                # FIX #6: skip if pattern requires short message but message is long
                if rule.requires_short_message and word_count > 5:
                    continue
                if re.search(rule.pattern, msg_lower):
                    # Keep the highest confidence score for this intent
                    if intent not in results or results[intent] < rule.confidence:
                        results[intent] = rule.confidence
                    logger.debug(f"Rule match: {intent.value} (conf={rule.confidence:.2f}, "
                                 f"pattern={rule.pattern[:50]})")

        # FIX #3: Resolve mutual exclusion conflicts
        results = self._resolve_conflicts(results)

        # Special case: short message with history context → likely FOLLOWUP
        if not results and has_history and word_count <= 3:
            logger.info("🔗 Short message with history → FOLLOWUP")
            return [(Intent.FOLLOWUP, 0.65)]

        sorted_results = sorted(results.items(), key=lambda x: -x[1])
        return sorted_results

    def _resolve_conflicts(
        self,
        results: Dict[Intent, float]
    ) -> Dict[Intent, float]:
        """
        FIX #3: For each exclusive group, keep only the highest-confidence intent.
        """
        for group in EXCLUSIVE_INTENT_GROUPS:
            matched = [(i, results[i]) for i in group if i in results]
            if len(matched) > 1:
                # Keep only the winner
                winner = max(matched, key=lambda x: x[1])
                for intent, _ in matched:
                    if intent != winner[0]:
                        logger.debug(f"Conflict resolved: removed {intent.value} "
                                     f"in favour of {winner[0].value}")
                        del results[intent]
        return results


# ═══════════════════════════════════════════════════════════════════════════
# SEMANTIC CLASSIFIER  (FIX #4, #7)
# ═══════════════════════════════════════════════════════════════════════════

class SemanticClassifier:
    """
    FIX #4: Weighted keyword scoring instead of naive word overlap count.
    - Anchor keywords (highly specific) score much higher than generic words.
    - Uses TF-style weighting: rare/specific words carry more weight.

    FIX #7: Scores are normalised and bounded so they don't artificially
            inflate confidence for noisy short messages.
    """

    def __init__(self):
        self.intent_keywords   = self._build_keyword_sets()
        self.anchor_keywords   = {
            intent: set(kw.lower() for kw in kws)
            for intent, kws in ANCHOR_KEYWORDS.items()
        }

    def _build_keyword_sets(self) -> Dict[Intent, set]:
        """Build keyword sets from training examples."""
        keyword_sets: Dict[Intent, set] = {}
        for intent, examples in INTENT_EXAMPLES.items():
            keywords: set = set()
            for example in examples:
                keywords.update(re.findall(r'\w+', example.lower()))
            keyword_sets[intent] = keywords
        return keyword_sets

    def classify_multi(self, message: str) -> List[Tuple[Intent, float]]:
        """
        FIX #4: Score each intent using weighted keyword matching.
        Anchor keyword hit = 2× weight of regular keyword hit.
        Normalise by (query word count + 1) to penalise very short matches.

        Returns: sorted list of (Intent, confidence) tuples.
        """
        msg_lower = message.lower()
        words     = set(re.findall(r'\w+', msg_lower))

        if not words:
            return [(Intent.UNKNOWN, 0.0)]

        scores: Dict[Intent, float] = {}

        for intent, keywords in self.intent_keywords.items():
            if intent == Intent.ORDER_INPUT:
                # Skip — ORDER_INPUT handled by rule-based patterns only
                continue

            anchors  = self.anchor_keywords.get(intent, set())
            regular_hits = words & (keywords - anchors)
            anchor_hits  = words & anchors

            # FIX #4: anchor words count double
            weighted_score = len(regular_hits) * 1.0 + len(anchor_hits) * 2.0

            if weighted_score > 0:
                # FIX #7: normalise; cap at 0.85 for semantic classifier
                norm_score = weighted_score / (len(words) + 1)
                confidence = min(0.85, norm_score * INTENT_BASE_CONFIDENCE.get(intent, 0.75))
                scores[intent] = confidence

        # Only return intents above a meaningful threshold
        threshold = 0.30
        results = sorted(
            [(i, s) for i, s in scores.items() if s >= threshold],
            key=lambda x: -x[1]
        )
        return results


# ═══════════════════════════════════════════════════════════════════════════
# CLASSIFICATION RESULT DATACLASS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class IntentResult:
    """
    Structured result from classify_multi().
    Holds the primary intent plus any secondary intents (multi-intent support).
    """
    primary: Intent
    primary_confidence: float
    # All detected intents, sorted by confidence (includes primary)
    all_intents: List[Tuple[Intent, float]] = field(default_factory=list)
    source: str = "unknown"  # "rule", "semantic", "llm", "fallback"

    @property
    def secondary_intents(self) -> List[Intent]:
        """All intents except the primary one."""
        return [i for i, _ in self.all_intents if i != self.primary]

    @property
    def requires_db(self) -> bool:
        return any(is_database_intent(i) for i, _ in self.all_intents)

    @property
    def requires_policy(self) -> bool:
        return any(is_policy_intent(i) for i, _ in self.all_intents)

    @property
    def requires_tech_support(self) -> bool:
        return any(is_technical_support_intent(i) for i, _ in self.all_intents)

    def __str__(self) -> str:
        lines = [f"Primary : {self.primary.value} (conf={self.primary_confidence:.2f}) [{self.source}]"]
        for i, c in self.all_intents:
            if i != self.primary:
                lines.append(f"Secondary: {i.value} (conf={c:.2f})")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# HYBRID INTENT CLASSIFIER  (ALL FIXES)
# ═══════════════════════════════════════════════════════════════════════════

class HybridIntentClassifier:
    """
    Combines multiple classification strategies:
    1. Rule-based   – fast, high precision, collects ALL matches
    2. Semantic     – weighted keyword matching, fills gaps
    3. LLM fallback – accurate for complex/ambiguous messages

    FIX #1: Returns IntentResult with all_intents list (multi-intent support).
    FIX #2: Rule and semantic classifiers both collect all matches.
    """

    def __init__(self):
        self.rule_classifier     = RuleBasedClassifier()
        self.semantic_classifier = SemanticClassifier()
        self.stats = {'rule': 0, 'semantic': 0, 'llm': 0, 'fallback': 0, 'total': 0}

    # ── PUBLIC API ────────────────────────────────────────────────────────

    def classify(
        self,
        message: str,
        has_history: bool = False,
        use_llm: Optional[callable] = None,
        top_k: int = 3,
    ) -> IntentResult:
        """
        FIX #1: Returns IntentResult containing primary intent AND
                all secondary intents detected (multi-intent).

        Args:
            message:     User message.
            has_history: Whether conversation has previous turns.
            use_llm:     Optional callable (message) → (Intent, float).
            top_k:       Max number of intents to return.

        Returns:
            IntentResult with primary and all secondary intents.
        """
        self.stats['total'] += 1
        msg = message.strip()

        # ─────────────────────────────────────────────────────────────────
        # Step 1: Rule-based — always run first (fast)
        # ─────────────────────────────────────────────────────────────────
        rule_results = self.rule_classifier.classify_multi(msg, has_history)

        if rule_results and rule_results[0][1] >= 0.80:
            # High-confidence rule hit — also try semantic to find secondaries
            sem_results  = self.semantic_classifier.classify_multi(msg)
            merged       = self._merge_results(rule_results, sem_results, top_k)
            self.stats['rule'] += 1
            return self._build_result(merged, source="rule")

        # ─────────────────────────────────────────────────────────────────
        # Step 2: Semantic — combine with any partial rule results
        # ─────────────────────────────────────────────────────────────────
        sem_results = self.semantic_classifier.classify_multi(msg)
        merged      = self._merge_results(rule_results, sem_results, top_k)

        if merged and merged[0][1] >= 0.45:
            self.stats['semantic'] += 1
            return self._build_result(merged, source="semantic")

        # ─────────────────────────────────────────────────────────────────
        # Step 3: LLM fallback — for ambiguous or complex messages
        # ─────────────────────────────────────────────────────────────────
        if use_llm:
            try:
                llm_results = llm_classify_multi_intent(msg, use_llm)
                if llm_results and llm_results[0][1] >= 0.40:
                    self.stats['llm'] += 1
                    return self._build_result(llm_results[:top_k], source="llm")
            except Exception as exc:
                logger.warning(f"LLM classification failed: {exc}")

        # ─────────────────────────────────────────────────────────────────
        # Fallback: return best partial result or UNKNOWN
        # ─────────────────────────────────────────────────────────────────
        self.stats['fallback'] += 1
        if merged:
            return self._build_result(merged, source="fallback")
        return IntentResult(
            primary=Intent.UNKNOWN,
            primary_confidence=0.0,
            all_intents=[(Intent.UNKNOWN, 0.0)],
            source="fallback",
        )

    # ── INTERNAL HELPERS ──────────────────────────────────────────────────

    @staticmethod
    def _merge_results(
        rule_results: List[Tuple[Intent, float]],
        sem_results:  List[Tuple[Intent, float]],
        top_k: int,
    ) -> List[Tuple[Intent, float]]:
        """
        Merge rule and semantic results.
        Rule results take precedence; semantic fills in undetected intents.
        If an intent appears in both, keep the higher confidence score.
        """
        merged: Dict[Intent, float] = {}
        for intent, conf in rule_results:
            merged[intent] = conf
        for intent, conf in sem_results:
            # Only add if not already present, or if semantic is higher
            if intent not in merged or merged[intent] < conf:
                merged[intent] = conf

        # Sort by confidence descending, return top_k
        return sorted(merged.items(), key=lambda x: -x[1])[:top_k]

    @staticmethod
    def _build_result(
        results: List[Tuple[Intent, float]],
        source: str,
    ) -> IntentResult:
        if not results:
            return IntentResult(Intent.UNKNOWN, 0.0, [(Intent.UNKNOWN, 0.0)], source)
        primary, primary_conf = results[0]
        logger.info(
            f"✅ [{source}] Primary={primary.value} ({primary_conf:.2f})"
            + (f" | Secondary={[i.value for i, _ in results[1:]]}" if len(results) > 1 else "")
        )
        return IntentResult(
            primary=primary,
            primary_confidence=primary_conf,
            all_intents=results,
            source=source,
        )

    def get_stats(self) -> Dict:
        total = self.stats['total']
        if total == 0:
            return {}
        return {
            'total':    total,
            'rule':     f"{self.stats['rule']} ({self.stats['rule'] / total * 100:.1f}%)",
            'semantic': f"{self.stats['semantic']} ({self.stats['semantic'] / total * 100:.1f}%)",
            'llm':      f"{self.stats['llm']} ({self.stats['llm'] / total * 100:.1f}%)",
            'fallback': f"{self.stats['fallback']} ({self.stats['fallback'] / total * 100:.1f}%)",
        }


# ═══════════════════════════════════════════════════════════════════════════
# LLM FALLBACK — MULTI-INTENT  (FIX #1)
# ═══════════════════════════════════════════════════════════════════════════

def llm_classify_multi_intent(
    message: str,
    llm,
    max_intents: int = 3,
) -> List[Tuple[Intent, float]]:
    """
    FIX #1: LLM now returns a LIST of intents, not just one.
    Prompt instructs the model to detect all applicable intents.
    """
    prompt = f"""You are classifying a Myanmar phone shop customer message.
The message may express MORE THAN ONE intent simultaneously.

Message: "{message}"

Intent categories (you may pick up to {max_intents} that apply):
- greeting          : Greetings — hello, hi, မင်္ဂလာပါ
- casual            : Casual chat, thank you, bye, okay
- crm_question      : Shop location, phone number, opening hours, warranty, refund, payment method
- technical_support : How to use a phone, troubleshooting, settings, wifi/bluetooth issues, factory reset
- brand_list        : Asking what brands are available
- model_list        : Asking for models of a specific brand (e.g. "show Samsung phones")
- price_filter      : Filtering by price/budget (e.g. "under 5 lakh")
- spec_search       : Features — camera, battery, gaming, 5G, fast charging
- ram_storage_search: Specific RAM or storage (e.g. "8GB RAM", "256GB storage")
- color_search      : Asking about colors (e.g. "black phone", "what colors available")
- comparison        : Comparing two or more models (e.g. "iPhone vs Samsung")
- recommendation    : Asking for advice or suggestions
- stock_check       : Checking if a specific model is in stock
- buy_product       : Explicit purchase intent (e.g. "I want to buy this")
- cart_command      : Cart management — view cart, add to cart, checkout
- order_input       : Providing delivery info — address, phone number, name, township
- followup          : Referencing prior conversation context (e.g. "how much for that one?")
- unknown           : Irrelevant or gibberish

Return ONLY valid JSON — no markdown, no explanation:
{{
    "intents": [
        {{"intent": "intent_name", "confidence": 0.0}},
        {{"intent": "intent_name", "confidence": 0.0}}
    ],
    "reason": "brief explanation"
}}

Order intents by confidence descending. Include only intents with confidence >= 0.4."""

    import json

    try:
        # Support both LangChain LLM objects (.invoke) and plain callables
        if hasattr(llm, 'invoke'):
            response = llm.invoke(prompt)
            content  = response.content.strip()
        else:
            raw = llm(prompt)

            # ── Fast path: callable already returned parsed intent tuples ──
            if isinstance(raw, list) and raw and isinstance(raw[0], tuple):
                results: List[Tuple[Intent, float]] = []
                for item in raw:
                    intent, confidence = item[0], float(item[1])
                    if not isinstance(intent, Intent):
                        try:
                            intent = Intent(intent)
                        except ValueError:
                            intent = Intent.UNKNOWN
                    results.append((intent, confidence))
                return sorted(results, key=lambda x: -x[1])

            # ── Slow path: callable returned a string, parse as JSON ──
            content = raw.content if hasattr(raw, 'content') else str(raw)
            content = content.strip()

        content  = re.sub(r'```json\s*|\s*```', '', content).strip()
        logger.debug(f"LLM raw response: {repr(content)}")
        if not content:
            raise ValueError("LLM returned empty response")
        data     = json.loads(content)

        results: List[Tuple[Intent, float]] = []
        for item in data.get("intents", []):
            intent_str = item.get("intent", "unknown")
            confidence = float(item.get("confidence", 0.5))
            try:
                intent = Intent(intent_str)
            except ValueError:
                intent = Intent.UNKNOWN
            results.append((intent, confidence))

        return sorted(results, key=lambda x: -x[1])

    except Exception as exc:
        logger.error(f"LLM multi-intent classification error: {exc} | raw={repr(content) if 'content' in dir() else 'N/A'}")
        return [(Intent.UNKNOWN, 0.0)]


# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

_DB_INTENTS = {
    Intent.BRAND_LIST, Intent.MODEL_LIST, Intent.PRICE_FILTER,
    Intent.SPEC_SEARCH, Intent.RAM_STORAGE_SEARCH, Intent.COLOR_SEARCH,
    Intent.COMPARISON, Intent.RECOMMENDATION, Intent.STOCK_CHECK,
}

def is_database_intent(intent: Intent) -> bool:
    """Returns True if intent requires database access."""
    return intent in _DB_INTENTS

def is_policy_intent(intent: Intent) -> bool:
    """Returns True if intent requires shop policy knowledge."""
    return intent == Intent.CRM_QUESTION

def is_technical_support_intent(intent: Intent) -> bool:
    """Returns True if intent is technical support."""
    return intent == Intent.TECHNICAL_SUPPORT

def is_ordering_intent(intent: Intent) -> bool:
    """Returns True if intent is part of the ordering flow."""
    return intent in {Intent.BUY_PRODUCT, Intent.CART_COMMAND, Intent.ORDER_INPUT}


# ═══════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE & TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)  # Set to DEBUG to see all rule hits

    classifier = HybridIntentClassifier()

    test_cases = [
        # ── Single intent ──────────────────────────────────────────────
        ("hello",                              [Intent.GREETING]),
        ("ကျေးဇူးပါ",                          [Intent.CASUAL]),
        ("ဆိုင် ဘယ်မှာလဲ?",                    [Intent.CRM_QUESTION]),
        ("wifi မတက်ဘူး",                       [Intent.TECHNICAL_SUPPORT]),
        ("8GB RAM ဖုန်းတွေ",                   [Intent.RAM_STORAGE_SEARCH]),
        ("black color ရှိလား",                 [Intent.COLOR_SEARCH]),
        ("iphone vs samsung ဘယ်ဟာပိုကောင်း",   [Intent.COMPARISON]),
        ("ဒါ ဝယ်မယ်",                          [Intent.BUY_PRODUCT]),
        ("cart ကြည့်ချင်တယ်",                  [Intent.CART_COMMAND]),
        ("လိပ်စာ ကတော့ မြောက်ဒဂုံ",           [Intent.ORDER_INPUT]),

        # ── Multi-intent (the main fix) ────────────────────────────────
        # "Samsung phones under 5 lakh" → MODEL_LIST + PRICE_FILTER
        ("Samsung ဖုန်း 5 သိန်းအောက်",         [Intent.MODEL_LIST, Intent.PRICE_FILTER]),
        # "8GB RAM under 3 lakh" → RAM_STORAGE_SEARCH + PRICE_FILTER
        ("8GB RAM 3 သိန်းအောက် ဖုန်း",         [Intent.RAM_STORAGE_SEARCH, Intent.PRICE_FILTER]),
        # "Samsung 8GB 256GB under 5 lakh" → MODEL_LIST + RAM + PRICE
        ("Samsung 8GB RAM 256GB 5 သိန်းအောက်", [Intent.MODEL_LIST, Intent.RAM_STORAGE_SEARCH, Intent.PRICE_FILTER]),
        # "Best camera phone with 5G" → SPEC_SEARCH + RECOMMENDATION
        ("best camera phone 5G recommend",      [Intent.SPEC_SEARCH, Intent.RECOMMENDATION]),

        # ── FIX #3: Conflict resolution ────────────────────────────────
        # "ဖုန်း မလုပ်ဘူး ဘယ်သူ ကူညီမလဲ" → TECHNICAL_SUPPORT, not CRM
        ("ဖုန်း မလုပ်ဘူး ဘယ်သူ ကူညီမလဲ",      [Intent.TECHNICAL_SUPPORT]),

        # ── FIX #6: FOLLOWUP tightened ────────────────────────────────
        # Long message with "this" should NOT be followup
        ("this phone has a great camera",       [Intent.SPEC_SEARCH]),
    ]

    print("=" * 70)
    print("  ADVANCED INTENT CLASSIFIER v3.0 — TEST RESULTS")
    print("=" * 70)

    passed = 0
    for query, expected_intents in test_cases:
        result = classifier.classify(query)
        detected = [i for i, _ in result.all_intents]

        # Check if all expected intents are in detected
        all_found = all(e in detected for e in expected_intents)
        status    = "✅ PASS" if all_found else "❌ FAIL"
        if all_found:
            passed += 1

        print(f"\n{status}  Query   : {query}")
        print(f"        Expected: {[i.value for i in expected_intents]}")
        print(f"        Got     : {result}")
        print(f"        DB={result.requires_db} | Policy={result.requires_policy} | Tech={result.requires_tech_support}")

    print("\n" + "=" * 70)
    print(f"  Results: {passed}/{len(test_cases)} passed")
    print("=" * 70)
    print("\nClassifier Stats:")
    print(classifier.get_stats())