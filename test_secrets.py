import os
import asyncio
import sqlite3
import random
import json
import yfinance as yf
from google import genai
from telegram import Bot
from dotenv import load_dotenv
from flow_god import analyze_with_ai_retry, fetch_news, get_performance_stats, format_telegram_msg

load_dotenv()

# Required Secrets
GEMINI_API_KEYS = [k.strip() for k in os.getenv('GEMINI_API_KEYS', '').split(',') if k.strip()]
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

async def run_comprehensive_test():
    print("--- Starting Institutional-Grade Integration Test ---")
    
    # 1. Simulate Scenario: "Golden Sweep" in a Mid-Cap stock
    fake_ticker = "PLTR"
    fake_trade_content = "🚨 UNUSUAL WHALES ALERT: PLTR $35 Calls expiring Friday. Volume: 50,000 contracts. Aggressive sweep detected."
    print(f"🔹 Simulated Scenario: {fake_ticker} (Golden Sweep Simulation)")

    # 2. Test Data Fetching
    print("🔹 Fetching Context Data...")
    news = fetch_news(fake_ticker)
    sec = fetch_news(fake_ticker, query_type="sec")
    print(f"✅ Context Fetch Complete")

    # 3. Test Gemini Analysis (Full Institutional Mode)
    print("🔹 Testing Gemini 3 Flash Preview (Golden Sweep + RVOL Mode)...")
    stats = get_performance_stats()
    daily_context = "Test Context: No other alerts today."
    
    market_data = (
        "Ticker: PLTR @ $32.50 | Market Cap: $72.4B | ADV: 45,000,000\n"
        "Technicals: RSI=62, 50SMA=$28.40\n"
        "Option Data: Strike $35 CALL, OI: 12,500, IV: 85%, Volume: 50,000 (GOLDEN SWEEP!)\n"
        "Macro: SPY: +0.40%, QQQ: +0.75%\n"
        "Earnings: 2026-05-05"
    )
    
    data = await analyze_with_ai_retry(fake_trade_content, news + "\n" + sec, stats, market_data, daily_context)
    
    if not data:
        print("❌ AI Analysis Failed")
        return

    print(f"✅ JSON Parsed. Golden Sweep Flag: {data.get('is_golden_sweep')}")

    # 4. Test Telegram Output
    print("🔹 Sending Institutional Signal to Telegram...")
    msg = format_telegram_msg(fake_ticker, data, stats)
    
    if TELEGRAM_TOKEN:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='HTML')
        print("✅ Institutional Signal Message Sent")
    else:
        print("⚠️ TELEGRAM_TOKEN missing, skipping message send.")

    # 5. Database Verification (Cleanup)
    with sqlite3.connect('flow_god.db') as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE ticker = ?", (fake_ticker,))
        conn.commit()
    print("✅ Cleanup Complete")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())
