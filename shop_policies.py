"""
╔══════════════════════════════════════════════════════════════════════════╗
║         COMPREHENSIVE SHOP POLICIES & CRM KNOWLEDGE BASE                 ║
║              Myanmar Mobile Phone Shop (Enhanced)                        ║
║         Covers ALL 15 Question Taxonomy Categories                       ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════
# SHOP BASIC INFORMATION
# ═══════════════════════════════════════════════════════════════════════════
POLICIES_AVAILABLE = True

SHOP_INFO = {
    "name": "Shwee Shaung Mobile",
    "name_myanmar": "ရွှေရှောင်း မိုဘိုင်းဆိုင်",

    "phone": "09-671698821",
    "phone_alt": "09-4355737883",
    "email": "shweeshaung@yourshop.com",
    "facebook": "https://facebook.com/ShweeShaungMobile",

    "address": "Gwat, Thaton",
    "address_myanmar": "ဂွတ်၊ သထုံမြို့",
    "map_link": "https://www.google.com/maps/place/16%C2%B053'18.2%22N+97%C2%B022'57.3%22E/@16.8883891,97.3777141,17z/data=!3m1!4b1!4m13!1m8!3m7!1s0x30c2e927355cabed:0x46135d6f5218bc9d!2sThaton,+Myanmar+(Burma)!3b1!8m2!3d16.9281519!4d97.36919!16zL20vMDNoYnY2!3m3!8m2!3d16.888384!4d97.382585?entry=ttu&g_ep=EgoyMDI2MDIxMS4wIKXMDSoASAFQAw%3D%3D",

    "business_hours": "9:00 AM - 7:00 PM (နေ့စဉ်)",
}

# ═══════════════════════════════════════════════════════════════════════════
# 1. PRODUCT INFORMATION (Answers: Taxonomy #1)
# ═══════════════════════════════════════════════════════════════════════════

PRODUCT_INFO_POLICY = """
# 📱 Product Information

## ဘာကို သိရှိနိုင်မလဲ:
✅ ဖုန်း model အမျိုးမျိုး
✅ Specifications (RAM, Storage, Camera, Battery)
✅ အရောင်များ ရရှိနိုင်မှု
✅ 5G support ရှိ/မရှိ
✅ Dual SIM ရှိ/မရှိ
✅ ဈေးနှုန်းများ

## ဘယ်လို မေးမြန်းရမလဲ:
• "Samsung ဖုန်းတွေ ဘာရှိလဲ?"
• "iPhone 14 က 5G ရှိလား?"
• "Redmi Note 13 ဘယ်အရောင်တွေ ရှိလဲ?"
• "ဒီဖုန်း dual SIM လား?"

## အချက်အလက် ရယူပုံ:
• Database မှ တိုက်ရိုက် ရယူထားသည်
• စမ်းသပ်စစ်ဆေးပြီး အချက်အလက်များ
• Brand တိုင်းအတွက် တိကျမှန်ကန်သော specification

📞 မေးမြန်းရန်: {phone}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 2. PRICE & PROMOTIONS (Answers: Taxonomy #2)
# ═══════════════════════════════════════════════════════════════════════════

PRICING_POLICY = """
# 💰 ဈေးနှုန်း နှင့် လျှော့ဈေးများ

## လက်ရှိ ဈေးနှုန်းများ:
✅ Database တွင် အခြေခံသော တိကျသောဈေးနှုန်း
✅ Myanmar Kyats (Ks) ဖြင့်သာ
✅ ကြိုတင် အသိပေးခြင်းမရှိဘဲ ပြောင်းလဲနိုင်သည်

## လျှော့ဈေးများ ရှိ/မရှိ:
• နေ့စဉ် စစ်ဆေးပါ
• ကျောင်းသား လျှော့ဈေးများ ရနိုင်သည် (မေးမြန်းပါ)
• Bulk orders (5+ လုံး): 3% လျှော့ဈေး
• Bulk orders (10+ လုံး): 5% လျှော့ဈေး

## အရစ်ကျ ဝယ်ယူခြင်း:
❌ **မရပါ** - Installment plans မရှိပါ
✅ Full payment သာ လက်ခံပါသည်

## Student Promotion:
✅ ကျောင်းသား card ပြရမည်
✅ ရွေးချယ်ထားသော model အချို့အတွက်သာ
✅ ဆိုင်တွင် မေးမြန်းပါ

## ဈေး နှိုင်းယှဉ်ခြင်း (Price Matching):
❌ ပြိုင်ဘက်ဆိုင်များနှင့် ဈေး မချိန်ပေးပါ
✅ ကျွန်ုပ်တို့သည် မူရင်းပစ္စည်းများ fair price ဖြင့် အာမခံပါသည်

📞 ဈေး စုံစမ်းရန်: {phone}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 3. PRODUCT COMPARISON (Answers: Taxonomy #3)
# ═══════════════════════════════════════════════════════════════════════════

COMPARISON_POLICY = """
# ⚖️ ဖုန်း နှိုင်းယှဉ်ခြင်း

## နှိုင်းယှဉ်နိုင်သည်များ:
✅ 2 ဖုန်း သို့မဟုတ် အများကြား နှိုင်းယှဉ်ပါ
✅ Features: Camera, Battery, RAM, Storage, Display
✅ ဈေး နှိုင်းယှဉ်ခြင်း
✅ Performance နှင့် use-case

## ဉပမာ မေးခွန်းများ:
• "Samsung A15 နဲ့ Redmi 13 ဘယ်ဟာကောင်းလဲ?"
• "iPhone 12 နဲ့ iPhone 13 ကွာခြားချက် ဘာလဲ?"
• "5 သိန်းအောက် အကောင်းဆုံး ဖုန်း ဘာလဲ?"

## နှိုင်းယှဉ် လုပ်ငန်းစဉ်:
1. Model 2 ခု ရွေးချယ်ပါ
2. ကျွန်ုပ်တို့က ထူးခြားချက်များ ပြသမည်
3. သင့်အတွက် သင့်လျော်သော ရွေးချယ်မှု ပြုလုပ်နိုင်သည်

## အသုံးပြုမှု အလိုက် ညွှန်ကြားချက်:
• Gaming: GPU, RAM, Display refresh rate
• Photography: Camera sensors, lens quality
• Battery: mAh, fast charging
• Budget: Best value for money

📞 နှိုင်းယှဉ်ရန် အကူအညီ: {phone}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 4. RECOMMENDATIONS (Answers: Taxonomy #4)
# ═══════════════════════════════════════════════════════════════════════════

RECOMMENDATION_POLICY = """
# 🎯 အကြံပြုချက်များ (Recommendations)

## သင့်အတွက် သင့်လျော်သော ဖုန်း ရှာပါ:

### Gaming အတွက်:
✅ မြင့်မားသော RAM (8GB+)
✅ ကောင်းမွန်သော GPU
✅ 90Hz+ display refresh rate
✅ ကြီးမားသော battery

### Camera အတွက်:
✅ 48MP+ main sensor
✅ OIS (optical stabilization)
✅ Night mode
✅ 4K video recording

### ကျောင်းသားများအတွက်:
✅ သင့်တော်သော ဈေးနှုန်း
✅ ကောင်းမွန်သော battery life
✅ Fast charging
✅ Durable build

### Battery Life အရှည်:
✅ 5000mAh+
✅ Power-efficient processor
✅ Fast charging support

## ဘယ်လို မေးမြန်းရမလဲ:
• "Gaming အတွက် ဖုန်း အကြံပြုပါ"
• "ငါ့ဘတ်ဂျက်အတွက် camera ကောင်းတဲ့ ဖုန်း"
• "ကျောင်းသားအတွက် သင့်တော်သော ဖုန်း"
• "Battery ကြာရှည်သော ဖုန်း အကြံပြုပါ"

## အကြံပြုချက် ပေးပုံ:
1. သင့် budget ပြောပါ
2. အဓိက အသုံးပြုမှု ပြောပါ (gaming, camera, etc.)
3. ကျွန်ုပ်တို့က အကောင်းဆုံး options ပေးမည်

📞 ကိုယ်ရေးကိုယ်တာ အကြံပြုချက်: {phone}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 5. AVAILABILITY & INVENTORY (Answers: Taxonomy #5)
# ═══════════════════════════════════════════════════════════════════════════

AVAILABILITY_POLICY = """
# 📦 လက်ကျန် Stock အခြေအနေ

## Stock စစ်ဆေးခြင်း:
✅ Real-time stock information
✅ "iPhone 15 ရှိသေးလား?" လို့ မေးနိုင်သည်
✅ အတိအကျ အရေအတွက် ပြောပြမည်

## Stock မရှိပါက:
• ပြန်လာမည့် ခန့်မှန်းရက် ပြောပြနိုင်သည်
• **ကြိုတင် မှာထားခြင်း (Reservation) မရပါ**
• ဦးစွာ ရောက်သူ ဦးစွာ ရမည် (First-come, first-served)
• ပုံမှန် ပြန်လည် စစ်ဆေးပါ

## အရောင် ရရှိနိုင်မှု:
• သီးခြား အရောင်များ အကန့်အသတ် ရှိနိုင်သည်
• အခြား အရောင်များ များသောအားဖြင့် ရနိုင်သည်
• သီးခြား အရောင် ရောက်မည့်ရက် အာမမခံနိုင်ပါ

## မှာကြိုးခြင်း (Pre-Orders):
❌ **Pre-orders မလက်ခံပါ**
✅ Stock ရှိသော ပစ္စည်းများ သာ ရောင်းချပါသည်

## မည်သည့် အရောင်များ ရရှိနိုင်လဲ:
• Model တစ်ခုချင်းအတွက် မတူညီနိုင်ပါ
• "Redmi Note 13 black ရှိလား?" လို့ မေးနိုင်သည်
• ကျွန်ုပ်တို့က လက်ရှိ ရရှိနိုင်သော အရောင်များ ပြောပြမည်

## မည်သည့်အချိန်တွင် Stock ပြန်ရောက်မည်လဲ:
• တိကျသော ရက်စွဲ မအာမမခံနိုင်ပါ
• Supplier မှ မူတည်သည်
• လာမည့် အစီအစဉ်များ ရှိပါက အသိပေးမည်

📞 Stock စုံစမ်းရန်: {phone}
📍 တည်နေရာ: {address}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 6. ORDER & PURCHASE PROCESS (Answers: Taxonomy #6)
# ═══════════════════════════════════════════════════════════════════════════

ORDER_PROCESS_POLICY = """
# 🛒 မှာယူခြင်း နှင့် ဝယ်ယူခြင်း လုပ်ငန်းစဉ်

## Order မှာယူပုံ:

### Online မှတစ်ဆင့်:
✅ ဤ chat မှတစ်ဆင့် မှာနိုင်သည်
✅ လုပ်ဆောင်ရန် အဆင့်များ:
   1. ဖုန်း ရွေးချယ်ပါ
   2. Cart ထဲထည့်ပါ
   3. ပို့ဆောင်ရန် လိပ်စာ ပေးပါ
   4. Payment method ရွေးပါ
   5. Order အတည်ပြုပါ
   6. Order number ရရှိမည်

### ဆိုင်၌ တိုက်ရိုက်:
✅ လာရောက်ရန်: {address}
✅ အချိန်: {business_hours}
✅ Cash သို့မဟုတ် mobile payment

## ပို့ဆောင်ခြင်း (Delivery):

### သထုံမြို့အတွင်း:
✅ **အခမဲ့ ပို့ဆောင်မည်** orders 1,000,000 Ks နှင့်အထက်
✅ 24-48 နာရီအတွင်း
✅ Same-day delivery: 12 PM မတိုင်မီ မှာပါက (100,000 Ks ခ)

### သထုံမြို့ပြင်ပ:
✅ Courier services မှတစ်ဆင့် ပို့နိုင်သည်
✅ Courier ခ ဝယ်သူ ကျခံရမည်
✅ 3-5 ရက် ပို့ဆောင်ချိန်

## Order ပယ်ဖျက်ခြင်း:
✅ မပို့မီ ပယ်ဖျက်နိုင်သည်
✅ Digital payments (KBZ/Wave):
   - 24 နာရီအတွင်း အပြည့်အဝ ပြန်အမ်းမည်
   - 3-5 ရက် ကြာနိုင်သည်
✅ Cash on Delivery:
   - ပယ်ဖျက်ခြင်းအတွက် ဒဏ်ရေး မရှိပါ

## Online နှင့် ဆိုင်၌ ယူခြင်း (Buy Online, Pickup In Store):
❌ လောလောဆယ် မရနိုင်သေးပါ
✅ Online မှာ၍ ပို့ဆောင်မှု သို့မဟုတ်
✅ ဆိုင်၌ တိုက်ရိုက် ဝယ်ယူမှု သာ

## Payment Methods:
✅ **Cash** - ဆိုင်၌ တိုက်ရိုက်
✅ **KBZ Pay** - 09-671698821
✅ **Wave Money** - 09-671698821

❌ **မလက်ခံသော Payment:**
- Credit/Debit Cards
- Installments
- Checks
- Foreign Currency

## Order ကို ဘယ်လို ခြေရာခံမလဲ:
✅ Order number ရရှိမည်
✅ Order number ပြ၍ status စစ်ဆေးနိုင်သည်
✅ ပို့ဆောင်ချိန်တွင် ဖုန်းဖြင့် အသိပေးမည်

📞 Order အကူအညီ: {phone}
📧 Email: {email}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 7. WARRANTY POLICY (Answers: Taxonomy #7)
# ═══════════════════════════════════════════════════════════════════════════

WARRANTY_POLICY = """
# 🛡️ အာမခံမူဝါဒ (Warranty Policy)

## အာမခံကာလ:

### Brand New ဖုန်းများ:
✅ **1 နှစ် တရားဝင်အာမခံ**
✅ တရားဝင် warranty center မှ ပေးသည်
✅ ဘောင်ချာ + အာမခံကတ် ပါရှိရမည်
✅ ဝယ်သည့်ရက်မှ စတင်သည်

### အာမခံ ကာမိသောအရာများ:
• ထုတ်လုပ်မှု ချို့ယွင်းချက်များ (Manufacturing defects)
• Hardware ပျက်စီးမှုများ (သုံးစွဲသူအမှားမဟုတ်ပါက)
• Software ပြဿနာများ (စက်ရုံမှ ဖြစ်သောအရာများ)
• Battery ချို့ယွင်းမှု (6 လအတွင်း ပျက်စီးပါက)

## အာမခံ မကာမိသောအရာများ:

❌ **ရေဝင်ခြင်း (Water Damage):**
- အရည် ဝင်ရောက်ခြင်း
- အစိုဓာတ် ပျက်စီးမှု
- Corrosion

❌ **ရုပ်ပိုင်းဆိုင်ရာ ပျက်စီးမှု:**
- မျက်နှာပြင် ကွဲခြင်း
- ကိုယ်ထည် ပျက်စီးခြင်း
- ကျရောက်၍ ပျက်စီးခြင်း
- အကြွေးအကြောင်း သို့မဟုတ် အရောင်ခြစ်ခြင်း

❌ **Software ပြုပြင်ခြင်းများ:**
- Root လုပ်ထားသော စက်များ
- Custom ROMs
- Jailbreak လုပ်ထားသော iPhone များ
- တရားမဝင် OS ပြုပြင်မှုများ

❌ **သုံးစွဲသူ အမှား:**
- မမှန်ကန်သော အသုံးပြုမှု
- တရားမဝင် accessories များ
- Third-party chargers ကြောင့် ပျက်စီးမှု
- အသုံးပြုမှု မှားယွင်း၍ ပူလွန်းခြင်း

## အာမခံ တောင်းဆိုပုံ:

**အဆင့် 1:** ဆိုင်သို့ ယူဆောင်လာပါ (ဖုန်း + ဘောင်ချာ + အာမခံကတ်)
**အဆင့် 2:** ကျွန်ုပ်တို့က စစ်ဆေးပြီး အတည်ပြုမည်
**အဆင့် 3:** အာမခံ ကာမိပါက:
   - Option A: ပြင်ဆင်ခြင်း (3-7 ရက်)
   - Option B: လဲလှယ်ခြင်း (stock ရှိပါက)
**အဆင့် 4:** အာမခံ မကာမိပါက:
   - ပြင်ဆင်ခ ကောက်ခံမည်
   - ခန့်မှန်းခ ကြိုတင်အသိပေးမည်

## မျက်နှာပြင် လဲလှယ်ခြင်း (Screen Replacement):
❌ မျက်နှာပြင် ကွဲခြင်း အာမခံ မကာပါ
✅ ပြင်ဆင်ခ ပေး၍ လဲလှယ်နိုင်သည်
• Model အလိုက် ဈေးကွာခြားသည်
• မူရင်း အစိတ်အပိုင်းများ အသုံးပြုသည်
• အစားထိုး မျက်နှာပြင် 30 ရက် အာမခံ

## Warranty Period စစ်ဆေးခြင်း:
• ဝယ်သည့်ရက်မှ စ၍ တွက်သည်
• မူရင်း ဝယ်ယူမှု ဘောင်ချာ ရှိရမည်
• ဝယ်ယူမှု အထောက်အထားဖြင့်သာ လွှဲပြောင်းနိုင်သည်

📞 အာမခံ စုံစမ်းရန်: {phone}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 8. TECHNICAL SUPPORT (Answers: Taxonomy #8)
# ═══════════════════════════════════════════════════════════════════════════

TECHNICAL_SUPPORT_POLICY = """
# 🔧 နည်းပညာ အထောက်အကူ (Technical Support)

## ကျွန်ုပ်တို့ ပံ့ပိုးသောအရာများ:

### ဝယ်မယူမီ:
✅ Feature ရှင်းလင်းချက်များ
✅ Specification အသေးစိတ်
✅ Model အကြံပြုချက်များ
✅ Compatibility မေးခွန်းများ

### ဝယ်ပြီးနောက် (အာမခံကာလအတွင်း):
✅ အခြေခံ troubleshooting
✅ Setup အကူအညီ
✅ Factory defect စစ်ဆေးခြင်း
✅ အာမခံတောင်းဆိုရာတွင် အကူအညီ

## ကျွန်ုပ်တို့ မပံ့ပိုးသောအရာများ:

❌ Software ပြဿနာများ (setup ပြီးနောက်):
- Virus ဖယ်ရှားခြင်း
- App installation
- Custom ROMs
- Performance optimization

❌ သုံးစွဲသူအမှား ပြဿနာများ:
- စကားဝှက် မေ့ခြင်း
- Account recovery
- Data ဆုံးရှုံးခြင်း
- မတော်တဆ ဖျက်ခြင်းများ

## အဖြစ်များသော ပြဿနာများ - အမြန် အကူအညီ:

**Battery မြန်မြန် ကုန်ခြင်း:**
• မသုံးသော apps များ ပိတ်ပါ
• Screen brightness လျှော့ပါ
• Location services ပိတ်ပါ
• Settings တွင် battery health စစ်ဆေးပါ

**ဖုန်း ပူလွန်းခြင်း:**
• အားသွင်းစဉ် phone case ချွတ်ပါ
• Resource-heavy apps များ ပိတ်ပါ
• အားသွင်းနေစဉ် မသုံးပါနှင့်
• Software updates စစ်ဆေးပါ

**Data လွှဲပြောင်းခြင်း:**
• ထုတ်လုပ်သူ၏ တရားဝင် transfer app သုံးပါ
• သို့မဟုတ် Google/iCloud backup သုံးပါ
• ဆိုင်တွင် အကူအညီ ရနိုင်သည်

**Android Version ပြင်ဆင်ခြင်း:**
• Settings → System → System Update
• သို့မဟုတ် ထုတ်လုပ်သူ support ဆက်သွယ်ပါ

## အကူအညီ ရယူနိုင်သည့် နေရာများ:

1. **ထုတ်လုပ်သူ Support:**
   - Samsung: [Official number]
   - Apple: Apple authorized centers
   - Xiaomi: Mi Service Center

2. **ကျွန်ုပ်တို့ ဆိုင်:**
   - အခြေခံ လမ်းညွှန်မှုများ သာ
   - အာမခံ ဆိုင်ရာ ပြဿနာများ
   - Hardware ပြဿနာများ

3. **Professional Repair:**
   - အာမခံပြင် ပြဿနာများအတွက်
   - ယုံကြည်ရသော ပြင်ဆင်ရေး ဆိုင်များ အကြံပြုနိုင်သည်

📞 Support: {phone}
⏰ အချိန်: {business_hours}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 9. ACCESSORIES (Answers: Taxonomy #9)
# ═══════════════════════════════════════════════════════════════════════════

ACCESSORIES_POLICY = """
# 🎧 Accessories နှင့် Add-ons

## ရရှိနိုင်သော Accessories:

✅ **ဖုန်းအိတ်များ (Phone Cases & Covers)**
- အမျိုးမျိုးသော brands နှင့် styles
- Model-specific နှင့် universal
- ဈေး: 5,000 - 50,000 Ks

✅ **Screen Protectors**
- Tempered glass
- Hydrogel film
- တပ်ဆင်ပေးခြင်း ဝန်ဆောင်မှု (1,000 Ks)

✅ **Chargers & Cables**
- original chargers
- Fast charging adapters
- USB-C / Lightning / Micro-USB cables

✅ **Power Banks**
- 10,000 mAh - 30,000 mAh
- အမျိုးမျိုးသော brands

✅ **Earphones & Headphones**
- Wired နှင့် wireless options
- Bluetooth earbuds
- Compatibility model အလိုက် ကွာခြားသည်

## မရောင်းချသော ပစ္စည်းများ:
❌ SIM cards (telecom shops များမှ ဝယ်ပါ)
❌ Smartwatches
❌ Tablets
❌ Laptops

## Accessory အာမခံ:
• Accessories များအတွက် 30 ရက် အာမခံ
• Branded items များအတွက် ထုတ်လုပ်သူ အာမခံ
• Cases/screen protectors များအတွက် အာမခံ မရှိပါ

## Bundle Deals:
✅ ဖုန်းဝယ်ပါက + accessories များ 10% လျှော့ဈေး
✅ လက်ရှိ bundle offers မေးမြန်းပါ

## Compatibility စစ်ဆေးခြင်း:
• ဝယ်မယူမီ compatibility စစ်ဆေးပေးနိုင်သည်
• Model-specific accessories များအတွက် ဝန်ထမ်းများကို မေးပါ

## Fast Charging Charger ရှိ/မရှိ:
✅ Fast charging chargers ရရှိနိုင်သည်
✅ Model ကိုက်ညီမှုကို စစ်ဆေးပေးမည်
• ဈေး model အလိုက် ကွာခြားသည်

## Earphones Compatibility:
• Wired: 3.5mm jack ရှိသော ဖုန်းများအတွက်
• Wireless: Bluetooth ပံ့ပိုးသော အားလုံး
• Model-specific ညွှန်ကြားချက်များ မေးပါ

📞 Accessories စုံစမ်းရန်: {phone}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 10. STORE INFO (Answers: Taxonomy #10 + #14)
# ═══════════════════════════════════════════════════════════════════════════

STORE_INFO_POLICY = """
# 🏪 ဆိုင် အချက်အလက်များ

## ဆိုင် နေရာ:
📍 **လိပ်စာ:** {address}
📍 **Myanmar:** {address_myanmar}
🗺️ **Map:** {map_link}

## ဖွင့်ချိန်များ:
⏰ **ပုံမှန်:** {business_hours}
⏰ **ပိတ်ရက်များ:** 10:00 AM - 5:00 PM
📅 **နေ့စဉ် ဖွင့်ထားသည်** (အထူးပိတ်ရက်များမှလွဲ၍)

## 24/7 ရရှိနိုင်မှု:
❌ **ကျွန်ုပ်တို့သည် 24/7 မဟုတ်ပါ**
✅ Business hours အတွင်းသာ
✅ အပြင်ပိုင်းတွင် message ချန်ထားနိုင်သည်
✅ နောက်တစ်ရက် business day တွင် ပြန်လည် ဆက်သွယ်မည်

## ဆိုင်ခွဲများ:
❌ ဆိုင်ခွဲ မရှိပါ
✅ တစ်ခုတည်းသော တည်နေရာ: {address}

## ကားရပ်နားရန်:
✅ ဆိုင်အနီး ကားရပ်နားနိုင်သည်
• အသေးစိတ် မေးမြန်းပါ

## ဘာသာစကား:
✅ Myanmar
✅ English
• ကျွန်ုပ်တို့၏ ဝန်ထမ်းများသည် နှစ်မျိုးလုံး ပြောနိုင်သည်

## ဘယ်လို ရောက်ရမလဲ:
• ကားဖြင့်, မော်တော်ဆိုင်ကယ်ဖြင့်, သို့မဟုတ် ခြေလျင်
• Google Maps ကို အသုံးပြုနိုင်သည်: {map_link}
• အကူအညီလိုပါက ဖုန်းဆက်ပါ: {phone}

📞 **ဆက်သွယ်ရန်:** {phone}
📞 **အခြား:** {phone_alt}
📧 **Email:** {email}
📱 **Facebook:** {facebook}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 11. RETURN & EXCHANGE POLICY (Answers: Taxonomy #11)
# ═══════════════════════════════════════════════════════════════════════════

RETURN_POLICY = """
# 🔄 ပြန်အမ်းခြင်း နှင့် လဲလှယ်ခြင်း မူဝါဒ

## အရေးကြီးသော အချက်: ပြန်မအမ်းပါ
❌ **ဝယ်ပြီးနောက် ပြန်မအမ်းပါ**
❌ ရောင်းချမှုအားလုံး အပြီးသတ်
❌ "စိတ်ပြောင်းပြီ" ဟူ၍ ပြန်အမ်း မရပါ

## ခြွင်းချက်များ (ချို့ယွင်းချက်ရှိသော ပစ္စည်းများ သာ):

✅ **ထုတ်လုပ်မှု ချို့ယွင်းချက် (7 ရက်အတွင်း):**
- ဘောက်စ် မဖွင့်ထားရမည်
- Factory-related ချို့ယွင်းချက် ဖြစ်ရမည်
- တူညီသော model သာ လဲလှယ်မည်
- စစ်ဆေးပြီးမှ ဆုံးဖြတ်မည်

## လဲလှယ်ခြင်း လုပ်ငန်းစဉ်:
1. ပစ္စည်း + ဘောင်ချာ 7 ရက်အတွင်း ယူလာပါ
2. မသုံးစွဲရသေးရမည်၊ မူရင်း packaging အတိုင်း
3. ကျွန်ုပ်တို့က ချို့ယွင်းချက် စစ်ဆေးမည်
4. အစစ်အမှန် ချို့ယွင်းချက် အတည်ပြုပါက:
   → တူညီသော model လဲလှယ်မည်
   → သို့မဟုတ် Store credit (ငွေပြန်မအမ်းပါ)

## ပြန်မအမ်းနိုင်သော ပစ္စည်းများ:
❌ ဖွင့်ပြီးသား ပစ္စည်းများ (box seal ကွဲပြီး)
❌ အသုံးပြုပြီး ပစ္စည်းများ
❌ Accessories များ
❌ SIM cards များ
❌ Promotion/discount ဖြင့် ဝယ်ယူသော ဖုန်းများ

## မကျေနပ်ပါက ဘာလုပ်ရမလဲ:
• ဆိုင်မှ မထွက်မီ သေချာစွာ စစ်ဆေးပါ
• မသေချာပါက ဆိုင်တွင် စမ်းသပ်ပါ
• ဝယ်မယူမီ မေးခွန်းအားလုံး မေးပါ

## ငွေပြန်အမ်းမှု (Refund):
❌ **ငွေသား ပြန်မအမ်းပါ**
✅ Store credit သာ (ချို့ယွင်းချက်ရှိသော items များအတွက်)
✅ 30 ရက် သက်တမ်း

## ပြန်အမ်းရန် ကာလ:
• ချို့ယွင်းချက်ရှိသော ပစ္စည်းများ: 7 ရက်
• Store credit အတွက်: 30 ရက်
• ငွေပြန်အမ်းခြင်း: မရှိပါ

## မည်သည့် items များ non-refundable လဲ:
❌ ပြန်မအမ်းနိုင်သောအရာများအားလုံး အထက်တွင် ဖော်ပြပြီးပြီ
❌ ပွင့်ထားသော ပစ္စည်းများ
❌ အသုံးပြုပြီး ပစ္စည်းများ
❌ Accessories

📞 မေးခွန်းများ: {phone}
📧 Email: {email}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 12. TRUST & AUTHENTICITY (Answers: Taxonomy #12)
# ═══════════════════════════════════════════════════════════════════════════

TRUST_POLICY = """
# 🔐 ယုံကြည်မှု၊ မူရင်းစစ်မှု နှင့် လုံခြုံရေး

## မူရင်း ဖုန်းများ:
✅ **100% မူရင်း အာမခံချက်**
✅ တရားဝင် distributors များမှ တိုက်ရိုက်
✅ Factory sealed boxes
✅ တရားဝင် warranty များ

## IMEI Verification:
✅ IMEI စစ်ဆေးပေးနိုင်သည်
✅ ဝယ်မယူမီ စစ်ဆေးပါ
✅ IMEI ကို manufacturer website တွင် စစ်ဆေးနိုင်သည်

## ဘယ်လို စစ်ဆေးရမလဲ:
1. ဖုန်းကို dial *#06# နှိပ်ပါ
2. IMEI number ပေါ်လာမည်
3. Box ပေါ်ရှိ IMEI နှင့် ယှဉ်ကြည့်ပါ
4. Manufacturer website တွင် IMEI စစ်ဆေးပါ

## Factory Unlocked:
✅ အများစု factory unlocked ဖြစ်သည်
✅ မည်သည့် SIM မဆို သုံးနိုင်သည်
✅ သီးခြား models များအတွက် မေးပါ

## Customer Data လုံခြုံရေး:
✅ လုံခြုံသော database storage
✅ ခွင့်ပြုထားသော ဝန်ထမ်းများသာ ဝင်ရောက်နိုင်သည်
✅ Third parties များနှင့် မျှဝေခြင်း မရှိပါ
✅ Online orders များအတွက် encrypted transmission

## ကျွန်ုပ်တို့ မလုပ်သောအရာများ:
❌ သင့်ဒေတာကို ရောင်းချခြင်း
❌ Marketing companies များနှင့် မျှဝေခြင်း
❌ Spam messages များ ပို့ခြင်း
❌ Order ထက်ပို၍ အသုံးပြုခြင်း

## Original Accessories:
✅ မူရင်း chargers များ ပါဝင်သည်
✅ မူရင်း earphones များ (model ပေါ်မူတည်၍)
✅ Official warranty cards

## Fake ဖုန်းများ:
❌ **ကျွန်ုပ်တို့တွင် အတုများ လုံးဝ မရှိပါ**
✅ မူရင်းစစ်မှုအတွက် သက်သေခံချက်များ ပေးနိုင်သည်
✅ တရားဝင် ထုတ်လုပ်သူ warranty

📞 အတည်ပြုရန်: {phone}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 13. FEEDBACK & COMPLAINTS (Answers: Taxonomy #13)
# ═══════════════════════════════════════════════════════════════════════════

FEEDBACK_POLICY = """
# 📢 တုံ့ပြန်ချက် နှင့် တိုင်ကြားချက်များ

## Feedback ပေးပုံ:

### အပြုသဘော Feedback:
✅ ကိုယ်တိုင် ပြောပါ
✅ Facebook တွင် review ရေးပါ: {facebook}
✅ Email: {email}
✅ ကျေးဇူးတင်ပါသည်!

### တိုင်ကြားချက်များ:
📧 **Email (အကောင်းဆုံး):** {email}
📞 **ဖုန်း:** {phone}
🏪 **ကိုယ်တိုင်:** Manager နှင့် ပြောပါ - {address}

## Feedback အမျိုးအစားများ:

✅ **ဝန်ဆောင်မှု အရည်အသွေး:**
- ဝန်ထမ်း အပြုအမူ
- တုံ့ပြန်မှု အချိန်
- အကူအညီ ပေးမှု

✅ **ပစ္စည်း ပြဿနာများ:**
- ချို့ယွင်းချက်ရှိသော ပစ္စည်းများ
- မှားသော specifications
- အရည်အသွေး ပူပန်မှုများ

✅ **လုပ်ငန်းစဉ် ပြဿနာများ:**
- မှာယူရာတွင် အခက်အခဲများ
- ငွေပေးချေမှု ပြဿနာများ
- ပို့ဆောင်မှု နှောင့်နှေးမှုများ

## တိုင်ကြားချက် ဖြေရှင်းခြင်း လုပ်ငန်းစဉ်:

**အဆင့် 1: တင်သွင်းခြင်း (Day 1)**
- Order number ပေးပါ
- ပြဿနာ ရှင်းလင်းစွာ ဖော်ပြပါ
- အထောက်အထား (ဓာတ်ပုံများ) ပါဝင်ပါက

**အဆင့် 2: အတည်ပြုချက် (2 နာရီအတွင်း)**
- ကျွန်ုပ်တို့က လက်ခံကြောင်း အတည်ပြုမည်
- Reference number ပေးမည်
- ဖြေရှင်းချိန် ခန့်မှန်းပြောမည်

**အဆင့် 3: စုံစမ်းစစ်ဆေးခြင်း (1-3 ရက်)**
- တိုင်ကြားချက် ပြန်လည်သုံးသပ်မည်
- အသေးစိတ် အတည်ပြုမည်
- သက်ဆိုင်ရာ ဝန်ထမ်းများနှင့် တိုင်ပင်မည်

**အဆင့် 4: ဖြေရှင်းခြင်း (3-7 ရက်)**
- ဖြေရှင်းချက် အဆိုပြုမည်
- ပြင်ဆင်မှု အကောင်အထည်ဖော်မည်
- သင့်ထံ ပြန်လည် ဆက်သွယ်မည်

## ဖြေရှင်းနိုင်သော နည်းလမ်းများ:

**ပစ္စည်း ပြဿနာများအတွက်:**
✅ လဲလှယ်/အစားထိုး
✅ ပြင်ဆင်ခြင်း
✅ Store credit (ငွေသား ပြန်မအမ်းပါ)

**ဝန်ဆောင်မှု ပြဿနာများအတွက်:**
✅ တောင်းပန်ချက်
✅ ဝန်ထမ်း ပြန်လည်သင်ကြားမှု
✅ နောက်တစ်ကြိမ် ဝယ်ယူမှုတွင် လျှော့ဈေး

## ကျွန်ုပ်တို့ မလုပ်နိုင်သောအရာများ:
❌ ငွေသား ပြန်အမ်းမှု (ရောင်းချမှုအားလုံး အပြီးသတ်)
❌ ကျိုးကြောင်းမညီသော တောင်းဆိုချက်များ
❌ အာမခံပြင် ထုတ်လုပ်သူ ချို့ယွင်းချက်များ ဖြေရှင်းခြင်း
❌ သုံးစွဲသူအမှား အတွက် လျော်ကြေးပေးခြင်း

## Feedback အားလုံးကို သုံးသပ်သည်:
✅ တိုင်ကြားချက်တိုင်းကို မှတ်တမ်းတင်သည်
✅ ဝန်ဆောင်မှု တိုးတက်ရန် အသုံးပြုသည်
✅ Feedback အပေါ် အခြေခံ၍ ဝန်ထမ်း သင်ကြားမှု ပြုပြင်သည်
✅ လုပ်ငန်းစဉ် တိုးတက်မှုများ အကောင်အထည်ဖော်သည်

## လူသိမရှိ Feedback:
✅ လူသိမရှိ feedback ပေးနိုင်သည်
• ပြဿနာ ဖြေရှင်းရန် အထောက်အကူ နည်းနိုင်သည်
• ရှေးဆက် တိုးတက်ရန်အတွက် တန်ဖိုး ရှိသေးသည်

## ပြီးနောက် Follow-Up:
• ဖြေရှင်းပြီးနောက် ဆက်သွယ်မည်
• ကျေနပ်မှု ရှိ/မရှိ မေးမည်
• ပြန်မဖြစ်အောင် စောင့်ကြည့်မည်

**ပျက်စီးသော ဖုန်း ရရှိပါက:**
1. ချက်ချင်း ဆက်သွယ်ပါ
2. ဓာတ်ပုံ ရိုက်ပါ
3. 24 နာရီအတွင်း ဖြေရှင်းမည်

**Human Agent နှင့် ပြောလိုပါက:**
✅ ဖုန်းခေါ်ပါ: {phone}
✅ ဆိုင်သို့ လာပါ
✅ "Human Agent လိုချင်တယ်" ပြောပါ

📧 **တိုင်ကြားရန်:** {email}
📞 **ဖုန်း:** {phone}
🏪 **လိပ်စာ:** {address_myanmar}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 14. CRM - CUSTOMER PROFILE & DATA MANAGEMENT (Answers: CRM Taxonomy #1, #12, #13)
# ═══════════════════════════════════════════════════════════════════════════

CRM_DATA_POLICY = """
# 👤 Customer Profile & Data Management

## Customer Profile ဖန်တီးခြင်း:
✅ ပထမဆုံး order တင်သည့်အခါ မှတ်ပုံတင်နိုင်သည်
✅ သို့မဟုတ် အချိန်မရွေး account ဖန်တီးနိုင်သည်
✅ အခမဲ့ ဖန်တီးနိုင်သည်

## Account Data:
• ကျွန်ုပ်တို့ သိမ်းဆည်းသည်: အမည်, ဖုန်း, လိပ်စာ သမိုင်း
• မသိမ်းဆည်းပါ: Payment details, စကားဝှက်များ
• ဖုန်းနံပါတ်ဖြင့် auto-login

## Contact Information ပြင်ဆင်ခြင်း:
✅ Email ပို့၍ ပြင်ဆင်နိုင်သည်: {email}
✅ ဖုန်းခေါ်၍ ပြင်ဆင်နိုင်သည်: {phone}
✅ ဆိုင်တွင် တိုက်ရိုက် ပြင်ဆင်နိုင်သည်

## Personal Data လုံခြုံရေး:
✅ လုံခြုံသော database ထဲတွင် သိမ်းဆည်းထားသည်
✅ ခွင့်ပြုထားသော ဝန်ထမ်းများသာ ဝင်ရောက်နိုင်သည်
✅ Third parties များနှင့် မျှဝေခြင်း မရှိပါ

## Multiple Accounts:
✅ ဖုန်းနံပါတ် တစ်ခုလျှင် account တစ်ခု
❌ တူညီသော ဖုန်းဖြင့် account များစွာ မရနိုင်ပါ

## Customer Data အသုံးပြုပုံ:
✅ Orders များ လုပ်ဆောင်ရန်
✅ ပစ္စည်းများ ပို့ဆောင်ရန်
✅ Customer support ပေးရန်
✅ Order updates များ ပို့ရန်
✅ အာမခံ အတည်ပြုရန်

## Data Protection Laws:
✅ ကျွန်ုပ်တို့သည် Myanmar data protection practices များ လိုက်နာသည်
✅ သင့် privacy ကို လေးစားသည်
✅ Data များကို ရောင်းချ သို့မဟုတ် အလွဲသုံးမှု မပြုလုပ်ပါ

## ကိုယ်ရေးကိုယ်တာ ပြဿနာများအတွက်:
📧 Email: {email}
📞 ဖုန်း: {phone}
⏰ 24 နာရီအတွင်း တုံ့ပြန်မည်

## Account ပိတ်ခြင်း:
✅ Email မှတစ်ဆင့် တောင်းဆိုပါ: {email}
✅ 7 ရက်အတွင်း ဖျက်မည်
✅ Order သမိုင်း legal/warranty ရည်ရွယ်ချက်များအတွက် သိမ်းဆည်းမည်
✅ Active orders များတွင် ဖျက်၍မရပါ

## ပြန်လည်အသုံးပြုခြင်း:
✅ ပိတ်ထားသော accounts များကို ပြန်ဖွင့်နိုင်သည်
✅ ယခင် order history ဆုံးရှုံးနိုင်သည်
✅ ပြန်ဖွင့်ခြင်းအတွက် ဒဏ်ရေး မရှိပါ

## Data ကို ဘယ်သူက ဝင်ရောက်နိုင်လဲ:
✅ ခွင့်ပြုထားသော ဝန်ထမ်းများသာ
✅ Order လုပ်ဆောင်ရန် လိုအပ်သောသူများ
❌ အခြားဆိုင်များ
❌ Marketing companies
❌ Social media platforms

## Third Parties များနှင့် မျှဝေခြင်း:
✅ **သာမန် မျှဝေသည်:**
- Delivery courier (အမည်, လိပ်စာ, ဖုန်း)
- Payment processor (transaction verification အတွက်)
- Law enforcement (ဥပဒေအရ လိုအပ်ပါက)

❌ **ဘယ်တော့မျှ မမျှဝေပါ:**
- အခြားဆိုင်များ
- Marketing companies
- Social media platforms
- Data brokers

## Data Record တောင်းခံခြင်း:
✅ သင့် data ကို တောင်းခံနိုင်သည်
✅ Email: {email}
✅ ကျွန်ုပ်တို့က 7 ရက်အတွင်း ပေးပို့မည်

📧 **Privacy ပူပန်မှုများအတွက်:** {email}
📞 **ဖုန်း:** {phone}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 15. LOYALTY & MEMBERSHIP (Answers: CRM Taxonomy #10, #11)
# ═══════════════════════════════════════════════════════════════════════════

LOYALTY_POLICY = """
# 🌟 Loyalty & Membership Program

## လက်ရှိ အခြေအနေ:
❌ **တရားဝင် Loyalty Program မရှိသေးပါ**

## မကြာမီ လာမည်:
🚧 ကျွန်ုပ်တို့ အစီအစဉ် ဆွဲနေသည်:
- Points system
- Member လျှော့ဈေးများ
- မွေးနေ့ အထူးများ
- Promotions များကို အစောဆုံး သိရှိခွင့်

## လက်ရှိ အကျိုးကျေးဇူးများ (ပုံမှန် ဝယ်သူများအတွက်):

✅ **Bulk လျှော့ဈေးများ:**
- 5+ ဖုန်းများ ဝယ်ယူပါက: 3% လျှော့ဈေး
- 10+ ဖုန်းများ ဝယ်ယူပါက: 5% လျှော့ဈေး
- Corporate orders: အထူး ဈေးနှုန်းများ

✅ **အကြိမ်များ ပြန်လည် ဝယ်သူများ အထူးခံစားခွင့်များ:**
- ဦးစားပေး customer service
- ပစ္စည်းသစ်များ ရောက်ရှိသည့်အခါ ပထမဆုံး အသိပေးခြင်း
- ရံဖန်ရံခါ အံ့ဩဖွယ် လျှော့ဈေးများ

## Points System မရှိပါ:
❌ လောလောဆယ် earn လုပ်ရန် points များ မရှိပါ
❌ Rewards card မရှိပါ
❌ Membership tiers မရှိပါ

## အနာဂတ် အစီအစဉ်များ:
🔜 မျှော်မှန်းထားသော Launch: 2026 ခုနှစ် အလယ်ပိုင်း
🔜 ရှိပြီးသား customers များအတွက် အလိုအလျောက် ပါဝင်မည်
🔜 ယခင် ဝယ်ယူမှုများအတွက် ကျောဘက်သို့ points (ဖြစ်နိုင်သည်)

## အသိပေး လက်ခံရန်:
📱 ကျွန်ုပ်တို့၏ Facebook ကို follow လုပ်ပါ: {facebook}
📧 Email updates များ subscribe လုပ်ပါ
📞 Notification list တွင် ထည့်ရန် ခေါ်ဆိုပါ

## Corporate/Bulk ဝယ်သူများ:
✅ အထူး program ရရှိနိုင်သည်
✅ အသေးစိတ်အတွက် ဆက်သွယ်ပါ: {email}
✅ Corporate rates အတွက် အနည်းဆုံး 10 units

## Promotional Messages:
• ကျွန်ုပ်တို့ promotions များ ပို့နိုင်သည်
• Opt-in လုပ်ပါက သာ
• Unsubscribe လွယ်ကူစွာ ပြုလုပ်နိုင်သည်
• တစ်လလျှင် အများဆုံး 2 messages

## Consent လိုအပ်ပါသလား:
✅ Marketing messages များအတွက် သင့် သဘောတူခွင့်ပြုချက် လိုအပ်သည်
✅ Order-related messages များအတွက် မလိုအပ်ပါ (လုံလောက်သော)

## Unsubscribe လုပ်ပုံ:
• "STOP" reply လုပ်ပါ
• သို့မဟုတ် Email: {email}
• ချက်ချင်း unsubscribe လုပ်ပေးမည်

📞 မေးခွန်းများ: {phone}
📧 Email: {email}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# 16. GENERAL FAQ (Answers: Remaining Taxonomy questions)
# ═══════════════════════════════════════════════════════════════════════════

GENERAL_FAQ = """
# ❓ အများလေ့လာမေးတတ်သော မေးခွန်းများ (FAQ)

## Q: သင်တို့စစ်မှန်သော ဆိုင် လား online သက်သက် လား?
A: ကျွန်ုပ်တို့ စစ်မှန်သော ရုပ်ပိုင်း ဆိုင် ဖြစ်သည်! လိပ်စာ: {address}

## Q: ဈေး ညှိနှိုင်း၍ ရပါသလား?
A: မရပါ, ကျွန်ုပ်တို့၏ ဈေးနှုန်းများ သတ်မှတ်ပြီး မျှတသည်။

## Q: အရစ်ကျ အစီအစဉ်များ ရှိပါသလား?
A: မရှိပါ, အပြည့်အဝ ငွေပေးချေမှု သာ (Cash, KBZ Pay, Wave Money)။

## Q: ဖုန်းအားလုံး မူရင်း ဖြစ်ပါသလား?
A: ဟုတ်ကဲ့, 100% စစ်မှန်သည်။ မူရင်းစစ်မှု အာမခံသည်။

## Q: ဖုန်းကို ဝယ်မယူမီ စမ်း၍ ရပါသလား?
A: ရပါသည်! ကျွန်ုပ်တို့ ဆိုင်သို့ လာ၍ သေချာစွာ စမ်းသပ်ပါ။

## Q: ဟောင်း ဖုန်းများ လဲလှယ်ပေးပါသလား?
A: မပေးပါ, ဟောင်း ဖုန်းများကို လဲလှယ်ခြင်းတွင် မလက်ခံပါ။

## Q: ဖုန်း reserve လုပ်၍ ရပါသလား?
A: မရပါ, reservation system မရှိပါ။ ဦးစွာ ရောက်သူ ဦးစွာ ရမည်။

## Q: Bulk orders များအတွက် ဈေး ညှိနှိုင်းပါသလား?
A: ရပါသည်! Bulk pricing အတွက် ဆက်သွယ်ပါ (5+ units)။

## Q: တစ်နိုင်ငံလုံး ပို့ဆောင်ပါသလား?
A: ရပါသည်, courier မှတစ်ဆင့်။ ဝယ်သူ shipping ခ ပေးရမည်။

## Q: Order ပျက်စီး၍ ရောက်ပါက?
A: ချက်ချင်း ဆက်သွယ်ပါ။ 24 နာရီအတွင်း ဖြေရှင်းမည်။

## Q: Order တင်ပြီးနောက် ပြောင်း၍ ရပါသလား?
A: မပို့မီသာ ရမည်။ ချက်ချင်း ဆက်သွယ်ပါ။

## Q: လိပ်စာ မှားပေးခဲ့ပါက?
A: ချက်ချင်း ဆက်သွယ်၍ ပြင်ဆင်ပါ။ ပို့ပြီးပါက မဖြစ်နိုင်ပါ။

## Q: Gift wrapping ရပါသလား?
A: မရပါ, ပုံမှန် packaging သာ။

## Q: တစ်ယောက်အတွက် ဝယ်ပေး၍ ရပါသလား?
A: ရပါသည်, သူတို့၏ delivery details ပေးပါ။

## Q: Return policy ဘာလဲ?
A: ပြန်မအမ်းပါ။ 7 ရက်အတွင်း ချို့ယွင်းချက်ရှိသော items များအတွက်သာ လဲလှယ်ပါ။

## Q: ပိတ်ရက်များတွင် ဖွင့်ပါသလား?
A: ရပါသည်, သို့သော် လျှော့ချချိန်များ: 10 AM - 5 PM။ အတည်ပြုရန် ဦးစွာ ခေါ်ဆိုပါ။

## Q: English ပြောနိုင်ပါသလား?
A: ရပါသည်, ကျွန်ုပ်တို့၏ ဝန်ထမ်းများ Myanmar နှင့် English နှစ်မျိုးလုံး ပြောသည်။

## Q: Bank transfer ဖြင့် ပေးနိုင်ပါသလား?
A: မရပါ, Cash, KBZ Pay, သို့မဟုတ် Wave Money သာ။

## Q: Delivery ဘယ်လောက် ကြာပါသလဲ?
A: သထုံမြို့: 24-48 နာရီ။ တစ်နိုင်ငံလုံး: 3-5 ရက်။

## Q: သင်တို့သည် AI ဖြစ်ပါသလား human ဖြစ်ပါသလား?
A: ကျွန်ုပ်သည် AI chatbot ဖြစ်သည်, သို့သော် human support အမြဲရရှိနိုင်သည်: {phone}

## Q: ကူညီနိုင်ပါသလား?
A: ဟုတ်ကဲ့! မည်သည့် မေးခွန်း မဆို မေးပါ သို့မဟုတ် {phone} ခေါ်ဆိုပါ။

## Q: 24/7 ရရှိနိုင်ပါသလား?
A: မရပါ, ကျွန်ုပ်တို့၏ hours: {business_hours}။ အပြင်တွင် message ချန်ထားပါ။

📞 နောက်ထပ် မေးခွန်းများ? ခေါ်ဆိုပါ: {phone}
📧 Email: {email}
🏪 လာရောက်ပါ: {address}
""".format(**SHOP_INFO)

# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_policy(category: str) -> str:
    """
    Get policy text by category
    Enhanced to cover ALL taxonomy categories
    """

    policies = {
        # Main categories
        "product_info": PRODUCT_INFO_POLICY,
        "pricing": PRICING_POLICY,
        "comparison": COMPARISON_POLICY,
        "recommendation": RECOMMENDATION_POLICY,
        "availability": AVAILABILITY_POLICY,
        "order_process": ORDER_PROCESS_POLICY,
        "warranty": WARRANTY_POLICY,
        "technical_support": TECHNICAL_SUPPORT_POLICY,
        "accessories": ACCESSORIES_POLICY,
        "store_info": STORE_INFO_POLICY,
        "return": RETURN_POLICY,
        "trust": TRUST_POLICY,
        "feedback": FEEDBACK_POLICY,
        "crm_data": CRM_DATA_POLICY,
        "loyalty": LOYALTY_POLICY,
        "faq": GENERAL_FAQ,

        # Aliases for backward compatibility
        "payment": PRICING_POLICY,
        "support": STORE_INFO_POLICY,
        "complaint": FEEDBACK_POLICY,
        "customer_service": STORE_INFO_POLICY,
        "privacy": CRM_DATA_POLICY,
        "account": CRM_DATA_POLICY,
        "shop_info": str(SHOP_INFO),
    }

    return policies.get(category.lower(), GENERAL_FAQ)


def detect_policy_category(message: str) -> str:
    """
    Detect which policy category - Enhanced for ALL taxonomy
    """

    message_lower = message.lower()

    # Specific patterns first (most specific to least specific)

    # Trust & Authenticity
    if any(word in message_lower for word in ['original', 'authentic', 'fake', 'imei', 'genuine',
                                                'factory unlock', 'မူရင်း', 'အစစ်', 'အတု']):
        return "trust"

    # Feedback & Complaints
    if any(word in message_lower for word in ['complaint', 'feedback', 'unhappy', 'disappointed',
                                                'damaged', 'broken', 'human agent', 'talk to',
                                                'ကန့်ကွက်', 'တိုင်ကြား', 'မကျေနပ်', 'ပျက်စီး']):
        return "feedback"

    # Technical Support
    if any(word in message_lower for word in ['battery drain', 'overheat', 'not working', 'how to',
                                                'transfer data', 'update', 'problem', 'issue',
                                                'ဘယ်လို', 'ပြဿနာ', 'အားသွင်း', 'ပူလွန်း']):
        return "technical_support"

    # Warranty (more specific)
    if any(word in message_lower for word in ['warranty', 'guarantee', 'defect', 'repair', 'claim',
                                                'screen replacement', 'အာမခံ', 'ပြင်ဆင်']):
        return "warranty"

    # Return & Exchange
    if any(word in message_lower for word in ['return', 'refund', 'exchange', 'non-refundable',
                                                'ပြန်အမ်း', 'လဲလှယ်']):
        return "return"

    # CRM & Data Privacy
    if any(word in message_lower for word in ['account', 'profile', 'personal data', 'privacy',
                                                'data protection', 'delete account', 'close account',
                                                'secure', 'third party', 'လုံခြုံ', 'အချက်အလက်']):
        return "crm_data"

    # Loyalty & Membership
    if any(word in message_lower for word in ['loyalty', 'member', 'points', 'reward', 'program',
                                                'earn', 'redeem']):
        return "loyalty"

    # Product Comparison
    if any(word in message_lower for word in ['compare', 'vs', 'versus', 'better', 'difference',
                                                'which is', 'နှိုင်းယှဉ်', 'ကောင်းတာ']):
        return "comparison"

    # Recommendations
    if any(word in message_lower for word in ['recommend', 'suggest', 'best for', 'good for',
                                                'gaming phone', 'camera phone', 'အကြံပြု', 'သင့်လျော်']):
        return "recommendation"

    # Pricing & Promotions
    if any(word in message_lower for word in ['price', 'cost', 'discount', 'promotion', 'installment',
                                                'cheap', 'expensive', 'ဈေး', 'လျှော့ဈေး', 'အရစ်']):
        return "pricing"

    # Availability & Stock
    if any(word in message_lower for word in ['available', 'stock', 'in stock', 'out of stock',
                                                'reserve', 'when arrive', 'ရှိလား', 'လက်ကျန်']):
        return "availability"

    # Order Process
    if any(word in message_lower for word in ['order', 'buy', 'purchase', 'checkout', 'delivery',
                                                'shipping', 'track', 'cancel', 'မှာယူ', 'ဝယ်', 'ပို့']):
        return "order_process"

    # Accessories
    if any(word in message_lower for word in ['case', 'cover', 'charger', 'cable', 'earphone',
                                                'power bank', 'screen protector', 'accessory',
                                                'ဖုန်းအိတ်', 'သော့ချ']):
        return "accessories"

    # Store Info & Contact
    if any(word in message_lower for word in ['location', 'address', 'hours', 'open', 'close',
                                                'contact', 'phone number', 'email', 'branch',
                                                '24/7', 'လိပ်စာ', 'ဖွင့်ချိန်', 'ဆက်သွယ်']):
        return "store_info"

    # Product Info
    if any(word in message_lower for word in ['specification', 'spec', 'feature', 'model', 'color',
                                                'dual sim', '5g', 'ram', 'storage', 'သတ်မှတ်ချက်']):
        return "product_info"

    # Default to FAQ for general questions
    return "faq"


# List all available policy categories
POLICIES_AVAILABLE_LIST = [
    "product_info", "pricing", "comparison", "recommendation", "availability",
    "order_process", "warranty", "technical_support", "accessories",
    "store_info", "return", "trust", "feedback", "crm_data", "loyalty", "faq"
]