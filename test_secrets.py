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
    print("--- Starting Insider Logic Integration Test ---")
    
    # 1. Simulate Scenario
    fake_ticker = "GOOGL"
    fake_trade_content = "🚨 UNUSUAL WHALES ALERT: GOOGL $180 Calls. Heavy flow before market close."
    print(f"🔹 Simulated Scenario: {fake_ticker}")

    # 2. Test Data Fetching
    print("🔹 Fetching Context Data (News + SEC)...")
    news = fetch_news(fake_ticker)
    sec = fetch_news(fake_ticker, query_type="sec")
    print(f"✅ Context Fetch Complete")

    # 3. Test Gemini Analysis (Insider Deep Dive)
    print("🔹 Testing Gemini 3 Flash (Insider Logic Mode)...")
    stats = get_performance_stats()
    entry_price = 172.50
    earnings_date = "2026-04-25"
    
    data = await analyze_with_ai_retry(fake_trade_content, news, stats, entry_price, earnings_date, sec)
    
    if data and isinstance(data, dict):
        print(f"✅ JSON Parsed. Insider evidence: {len(data.get('insider_logic', ''))} chars")
    else:
        print(f"❌ Gemini Analysis Failed")
        return

    # 4. Test Telegram Notification (Insider Layout)
    print("🔹 Testing Insider Evidence Template...")
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if tg_token and tg_chat_id:
        try:
            bot = Bot(token=tg_token)
            insider_tag = "🚨 <b>INSIDER ALERT</b>" if data['is_insider'] else "📊 <b>STANDARD FLOW</b>"
            final_msg = (
                f"🧪 <b>TEST: {fake_ticker} (INSIDER LOGIC)</b>\n"
                f"{insider_tag}\n"
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
                f"🔍 <b>INSIDER EVIDENCE:</b>\n"
                f"{data['insider_logic']}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🧐 <b>CRITICAL ANALYSIS:</b>\n"
                f"<i>{data['analysis']}</i>\n\n"
                f"📈 <i>{stats}</i>"
            )
            await bot.send_message(chat_id=tg_chat_id, text=final_msg, parse_mode='HTML')
            print("✅ Insider Evidence Message Sent")
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
