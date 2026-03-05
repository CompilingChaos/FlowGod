import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

async def send_variations():
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not tg_token or not tg_chat_id:
        print("Missing Telegram secrets")
        return

    bot = Bot(token=tg_token)
    
    variations = [
        ("18 chars", "━━━━━━━━━━━━━━━━━━"),
        ("16 chars", "━━━━━━━━━━━━━━━━"),
        ("14 chars", "━━━━━━━━━━━━━━"),
        ("12 chars", "━━━━━━━━━━━━"),
        ("10 chars", "━━━━━━━━━━")
    ]

    for label, sep in variations:
        msg = (
            f"🧪 <b>SEPARATOR TEST: {label}</b>\n"
            f"🚨 <b>INSIDER ALERT</b>\n"
            f"{sep}\n"
            f"🔥 <b>Conviction:</b> 9/10\n"
            f"🐋 <b>Meaning:</b> High Volume\n"
            f"{sep}\n"
            f"📊 <b>Action:</b> <code>LONG</code>\n"
            f"⚙️ <b>Leverage:</b> <code>10x</code>\n"
            f"{sep}\n"
            f"🎯 <b>Target:</b> <code>$150.0</code>\n"
            f"🛑 <b>Stop Loss:</b> <code>$135.0</code>\n"
            f"{sep}\n"
            f"🧐 <b>CRITICAL ANALYSIS:</b>\n"
            f"<i>Variation test for layout alignment.</i>"
        )
        await bot.send_message(chat_id=tg_chat_id, text=msg, parse_mode='HTML')
        print(f"Sent {label}")
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(send_variations())
