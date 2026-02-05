import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv

# မင်းရဲ့ logic.py ထဲက Function တွေကို လှမ်းခေါ်မယ်
import logic

load_dotenv()

# --- Config ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# စကားပြောမှတ်တမ်း သိမ်းရန်
user_history = {}


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_history[message.from_user.id] = []
    await message.answer("မင်္ဂလာပါ! Mya Phone Shop AI Assistant (Telegram) မှ ကြိုဆိုပါတယ်။")


@dp.message(F.text)
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_input = message.text

    # Typing ပြပေးခြင်း
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    history = user_history.get(user_id, [])
    selected_llm = logic.models["mistral-large"]

    try:
        # logic.py ထဲက prompt ထုတ်တဲ့ logic ကို သုံးမယ်
        # NVIDIA API Timeout ဖြစ်တတ်လို့ executor နဲ့ ခေါ်တာ ပိုစိတ်ချရတယ်
        loop = asyncio.get_event_loop()
        final_prompt = await loop.run_in_executor(
            None, logic.get_final_prompt, user_input, history, selected_llm
        )

        # AI ဆီက အဖြေတောင်းမယ်
        response = await selected_llm.ainvoke(final_prompt)
        ai_response = response.content

        # History Update
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": ai_response})
        user_history[user_id] = history[-10:]

        await message.answer(ai_response)

    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer("တောင်းပန်ပါတယ်ခင်ဗျာ၊ အချက်အလက်ရှာဖွေရာမှာ အမှားအယွင်းရှိနေလို့ ခဏနေမှ ပြန်မေးပေးပါ။")


async def main():
    print("Telegram Bot is starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())