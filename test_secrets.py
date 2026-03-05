import os
import random
import asyncio
import discord
import google.generativeai as genai
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

async def test_secrets():
    print("--- Starting Secret Validation Test ---")
    
    # 1. Test Discord Token
    discord_token = os.getenv('DISCORD_TOKEN')
    if discord_token:
        print(f"✅ DISCORD_TOKEN found (Length: {len(discord_token)})")
    else:
        print("❌ DISCORD_TOKEN missing!")

    # 2. Test Gemini API Keys
    gemini_keys = [k.strip() for k in os.getenv('GEMINI_API_KEYS', '').split(',') if k.strip()]
    if gemini_keys:
        print(f"✅ GEMINI_API_KEYS found ({len(gemini_keys)} keys detected)")
        # Test a random key with a simple prompt
        try:
            key = random.choice(gemini_keys)
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content("Hello, this is a secret test. Reply with 'OK'.")
            print(f"✅ Gemini API Test: {response.text.strip()}")
        except Exception as e:
            print(f"❌ Gemini API Test Failed: {e}")
    else:
        print("❌ GEMINI_API_KEYS missing!")

    # 3. Test Telegram
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if tg_token and tg_chat_id:
        print(f"✅ TELEGRAM_TOKEN and CHAT_ID found")
        try:
            bot = Bot(token=tg_token)
            await bot.send_message(chat_id=tg_chat_id, text="🚀 *FlowGod Secret Test:* Connection Successful!", parse_mode='Markdown')
            print("✅ Telegram Test Message Sent!")
        except Exception as e:
            print(f"❌ Telegram Test Failed: {e}")
    else:
        print("❌ Telegram Secrets missing!")

if __name__ == "__main__":
    asyncio.run(test_secrets())
