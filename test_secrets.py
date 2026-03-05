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
    print("--- Starting High-Quality UI Integration Test ---")
    
    # 1. Simulate Scenario
    fake_ticker = "AAPL"
    fake_trade_content = "🚨 UNUSUAL WHALES ALERT: AAPL $240 Puts. Massive institutional selling detected."
    print(f"🔹 Simulated Scenario: {fake_ticker}")

    # 2. Test News Fetching
    print("🔹 Testing News Fetch...")
    news = fetch_news(fake_ticker)
    print(f"✅ News Context Fetch Complete")

    # 3. Test Gemini Analysis (Strict JSON)
    print("🔹 Testing Gemini 3 Flash (Strict JSON Mode)...")
    stats = get_performance_stats()
    entry_price = 225.0
    data = await analyze_with_ai_retry(fake_trade_content, news, stats, entry_price)
    
    if data and isinstance(data, dict):
        print(f"✅ Strict JSON Parsed Successfully")
    else:
        print(f"❌ Gemini JSON Analysis Failed")
        return

    # 4. Test Telegram Notification (New High-Quality Layout)
    print("🔹 Testing High-Quality Telegram Notification...")
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if tg_token and tg_chat_id:
        try:
            bot = Bot(token=tg_token)
            final_msg = (
                f"🧪 <b>TEST: {fake_ticker} (UI OVERHAUL)</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔥 <b>Conviction:</b> {data['insider_conviction']}/10\n"
                f"🐋 <b>Meaning:</b> {data['meaningfulness']}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>Action:</b> <code>{data['direction']}</code>\n"
                f"⚙️ <b>Leverage:</b> <code>{data['leverage']}x</code>\n"
                f"⏱ <b>Timeframe:</b> <code>{data['timeframe_hours']}h</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>Target:</b> <code>${data['target_price']}</code>\n"
                f"🛑 <b>Stop Loss:</b> <code>${data['stop_loss']}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💡 <b>AI Insight:</b>\n"
                f"<i>{data['analysis']}</i>\n\n"
                f"📈 <i>{stats}</i>"
            )
            await bot.send_message(chat_id=tg_chat_id, text=final_msg, parse_mode='HTML')
            print("✅ High-Quality Telegram Message Sent")
        except Exception as e:
            print(f"❌ Telegram Failed: {e}")

    # 5. Cleanup
    print("🔹 Cleaning up...")
    with sqlite3.connect('flow_god.db') as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE ticker = ?", (fake_ticker,))
        conn.commit()
    print("✅ Cleanup Complete")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())
