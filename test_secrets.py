import os
import asyncio
import sqlite3
import random
import json
import yfinance as yf
from google import genai
from telegram import Bot
from dotenv import load_dotenv
from flow_god import analyze_with_ai_retry, fetch_news
from database import init_db, log_trade, get_performance_stats

load_dotenv()
init_db()

async def run_comprehensive_test():
    print("--- Starting Sophisticated System Integration Test ---")
    
    # 1. Simulate a Discord Message Scenario
    fake_ticker = "NVDA"
    fake_trade_content = "🚨 UNUSUAL WHALES ALERT: NVDA $140 Calls. Heavy institutional flow detected."
    print(f"🔹 Simulated Scenario: {fake_ticker}")

    # 2. Test News Fetching (Last 48h)
    print("🔹 Testing News Fetch...")
    news = fetch_news(fake_ticker)
    print(f"✅ News Context Length: {len(news)} chars")

    # 3. Test Gemini Analysis with New Prompt
    print("🔹 Testing Gemini 3 Flash (Advanced Logic)...")
    stats = get_performance_stats()
    entry_price = 120.0 # Simulated entry
    analysis = await analyze_with_ai_retry(fake_trade_content, news, stats, entry_price)
    
    if "Error" not in analysis:
        print("✅ Gemini Analysis Successful")
    else:
        print(f"❌ Gemini Analysis Failed: {analysis}")
        return

    # 4. Test JSON Parsing & Database Logging
    print("🔹 Testing JSON Parsing & Database Logging...")
    try:
        import re
        json_match = re.search(r'\{.*\}', analysis, re.DOTALL)
        data = json.loads(json_match.group())
        print(f"✅ Parsed AI Recommendations: {data}")
        
        log_trade(fake_ticker, data['direction'], data['leverage'], data['timeframe_hours'], 
                  data['conviction'], entry_price, data['target'], data['stop'])
        print("✅ Trade Logged with Target, Stop, and Conviction")
    except Exception as e:
        print(f"❌ DB Logging/Parsing Failed: {e}")

    # 5. Test Telegram Notification (HTML)
    print("🔹 Testing Telegram Notification (HTML)...")
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if tg_token and tg_chat_id:
        try:
            bot = Bot(token=tg_token)
            test_msg = f"🧪 <b>SOPHISTICATED TEST RUN:</b> {fake_ticker}\n\n{analysis}\n\n📊 {stats}"
            await bot.send_message(chat_id=tg_chat_id, text=test_msg, parse_mode='HTML')
            print("✅ Telegram HTML Notification Sent")
        except Exception as e:
            print(f"❌ Telegram Failed: {e}")

    # 6. Cleanup (Delete the test entry)
    print("🔹 Cleaning up test entry...")
    with sqlite3.connect('flow_god.db') as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE ticker = ?", (fake_ticker,))
        conn.commit()
    print("✅ Cleanup Complete")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())
