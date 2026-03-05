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
    print("--- Starting Strict JSON Integration Test ---")
    
    # 1. Simulate Scenario
    fake_ticker = "META"
    fake_trade_content = "🚨 UNUSUAL WHALES ALERT: META $500 Calls. Unusual size detected."
    print(f"🔹 Simulated Scenario: {fake_ticker}")

    # 2. Test News Fetching
    print("🔹 Testing News Fetch...")
    news = fetch_news(fake_ticker)
    print(f"✅ News Context Fetch Complete")

    # 3. Test Gemini Analysis (Strict JSON)
    print("🔹 Testing Gemini 3 Flash (Strict JSON Mode)...")
    stats = get_performance_stats()
    entry_price = 480.0
    data = await analyze_with_ai_retry(fake_trade_content, news, stats, entry_price)
    
    if data and isinstance(data, dict):
        print(f"✅ Strict JSON Parsed Successfully: {list(data.keys())}")
    else:
        print(f"❌ Gemini JSON Analysis Failed")
        return

    # 4. Test Database Logging
    print("🔹 Testing Database Logging...")
    try:
        log_trade(fake_ticker, data['direction'], data['leverage'], data['timeframe_hours'], 
                  data['insider_conviction'], entry_price, data['target_price'], data['stop_loss'])
        print("✅ Trade Logged Successfully")
    except Exception as e:
        print(f"❌ DB Logging Failed: {e}")

    # 5. Test Telegram Notification (Formatted from JSON)
    print("🔹 Testing Telegram Notification...")
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if tg_token and tg_chat_id:
        try:
            bot = Bot(token=tg_token)
            final_msg = (
                f"🧪 <b>STRICT JSON TEST: {fake_ticker}</b>\n\n"
                f"<b>Direction:</b> {data['direction']} ({data['leverage']}x)\n"
                f"<b>Conviction:</b> {data['insider_conviction']}/10\n"
                f"<b>Target:</b> ${data['target_price']}\n"
                f"<b>Stop:</b> ${data['stop_loss']}\n\n"
                f"<b>AI Analysis:</b>\n{data['analysis']}"
            )
            await bot.send_message(chat_id=tg_chat_id, text=final_msg, parse_mode='HTML')
            print("✅ Telegram HTML Notification Sent")
        except Exception as e:
            print(f"❌ Telegram Failed: {e}")

    # 6. Cleanup
    print("🔹 Cleaning up...")
    with sqlite3.connect('flow_god.db') as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE ticker = ?", (fake_ticker,))
        conn.commit()
    print("✅ Cleanup Complete")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())
