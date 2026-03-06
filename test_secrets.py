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
    print("--- Starting Institutional-Grade Integration Test ---")
    
    # 1. Simulate Scenario: "Golden Sweep" in a Mid-Cap stock
    fake_ticker = "PLTR"
    # Note: 50,000 contracts is massive compared to typical OI
    fake_trade_content = "🚨 UNUSUAL WHALES ALERT: PLTR $35 Calls expiring Friday. Volume: 50,000 contracts. Aggressive sweep detected."
    print(f"🔹 Simulated Scenario: {fake_ticker} (Golden Sweep Simulation)")

    # 2. Test Data Fetching
    print("🔹 Fetching Context Data...")
    news = fetch_news(fake_ticker)
    sec = fetch_news(fake_ticker, query_type="sec")
    print(f"✅ Context Fetch Complete")

    # 3. Test Gemini Analysis (Full Institutional Mode)
    print("🔹 Testing Gemini 3 Flash (Golden Sweep + RVOL Mode)...")
    stats = get_performance_stats()
    
    # Simulated Market Data with Vol > OI
    market_data = (
        "Ticker: PLTR @ $32.50 | Market Cap: $72.4B | ADV: 45,000,000\n"
        "Technicals: RSI=62, 50SMA=$28.40\n"
        "Option Data: Strike $35 CALL, OI: 12,500, IV: 85%, Volume: 50,000 (GOLDEN SWEEP!)\n"
        "Macro: SPY: +0.40%, QQQ: +0.75%\n"
        "Earnings: 2026-05-05"
    )
    
    data = await analyze_with_ai_retry(fake_trade_content, news + "\n" + sec, stats, market_data)
    
    if data and isinstance(data, dict):
        print(f"✅ JSON Parsed. Golden Sweep Flag: {data.get('is_golden_sweep')}")
    else:
        print(f"❌ Gemini Analysis Failed")
        return

    # 4. Test Telegram Notification (Advanced Layout)
    print("🔹 Sending Institutional Signal to Telegram...")
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if tg_token and tg_chat_id:
        try:
            bot = Bot(token=tg_token)
            insider_tag = "🚨 <b>INSIDER ALERT</b>" if data['is_insider'] else "📊 <b>STANDARD FLOW</b>"
            golden_tag = "🏆 <b>GOLDEN SWEEP DETECTED</b>\n" if data.get('is_golden_sweep') else ""
            iv_msg = "HIGH IV RISK" if data['iv_warning'] is True else data['iv_warning']
            iv_box = f"⚠️ <b>{iv_msg}</b>\n━━━━━━━━━━━━━━━━━\n" if data['iv_warning'] else ""
            
            final_msg = (
                f"🧪 <b>TEST: {fake_ticker} (INSTITUTIONAL UI)</b>\n"
                f"{insider_tag}\n"
                f"{golden_tag}"
                f"━━━━━━━━━━━━━━━━━\n"
                f"{iv_box}"
                f"🔥 <b>Conviction:</b> {data['insider_conviction']}/10\n"
                f"🐋 <b>Meaning:</b> {data['meaningfulness']}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>Action:</b> <code>{data['direction']}</code>\n"
                f"⚙️ <b>Leverage:</b> <code>{data['leverage']}x</code>\n"
                f"⏱ <b>Timeframe:</b> <code>{data['timeframe_hours']}h</code>\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>Target:</b> <code>${data['target_price']}</code>\n"
                f"🛑 <b>Stop Loss:</b> <code>${data['stop_loss']}</code>\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🔍 <b>INSIDER EVIDENCE:</b>\n"
                f"{data['insider_logic']}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🧐 <b>CRITICAL ANALYSIS:</b>\n"
                f"<i>{data['analysis']}</i>\n\n"
                f"📈 <i>{stats}</i>"
            )
            await bot.send_message(chat_id=tg_chat_id, text=final_msg, parse_mode='HTML')
            print("✅ Institutional Signal Message Sent")
        except Exception as e:
            print(f"❌ Telegram Failed: {e}")

    # 5. Cleanup
    with sqlite3.connect('flow_god.db') as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE ticker = ?", (fake_ticker,))
        conn.commit()
    print("✅ Cleanup Complete")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())
