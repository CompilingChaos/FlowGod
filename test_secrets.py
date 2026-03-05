import os
import asyncio
import sqlite3
import random
import yfinance as yf
from google import genai
from telegram import Bot
from dotenv import load_dotenv
from flow_god import analyze_with_ai_retry, fetch_news
from database import init_db, log_trade, get_performance_stats

load_dotenv()
init_db()

async def run_comprehensive_test():
    print("--- Starting Full System Integration Test ---")
    
    # 1. Simulate a Discord Message Scenario
    fake_ticker = "TSLA"
    fake_trade_content = "🚨 UNUSUAL WHALES ALERT: TSLA $250 Calls expiring Friday. Size: $2.4M. Aggressive buying detected."
    print(f"🔹 Simulated Scenario: {fake_ticker}")

    # 2. Test News Fetching (Last 24h logic)
    print("🔹 Testing News Fetch (googlesearch-python)...")
    news = fetch_news(fake_ticker)
    print(f"✅ News Context Length: {len(news)} chars")

    # 3. Test Gemini Analysis (google-genai)
    print("🔹 Testing Gemini 3 Flash Analysis...")
    stats = get_performance_stats()
    analysis = await analyze_with_ai_retry(fake_trade_content, news, stats)
    if "Error" not in analysis:
        print("✅ Gemini Analysis Successful")
    else:
        print(f"❌ Gemini Analysis Failed: {analysis}")
        return

    # 4. Test Database Logging
    print("🔹 Testing Database Logging (SQLite)...")
    try:
        log_trade(fake_ticker, "LONG", 10, "24h", 250.0)
        print("✅ Trade Logged to Database")
    except Exception as e:
        print(f"❌ DB Logging Failed: {e}")

    # 5. Test Telegram Notification
    print("🔹 Testing Telegram Notification...")
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if tg_token and tg_chat_id:
        try:
            bot = Bot(token=tg_token)
            test_msg = f"🧪 *TEST RUN:* {fake_ticker}\n\n{analysis}\n\n📊 {stats}"
            await bot.send_message(chat_id=tg_chat_id, text=test_msg, parse_mode='Markdown')
            print("✅ Telegram Test Message Sent")
        except Exception as e:
            print(f"❌ Telegram Failed: {e}")

    # 6. Cleanup (Delete the test entry)
    print("🔹 Cleaning up test entry from database...")
    with sqlite3.connect('flow_god.db') as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE ticker = ?", (fake_ticker,))
        conn.commit()
    print("✅ Cleanup Complete. Database remains clean.")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())
