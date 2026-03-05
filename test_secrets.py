import os
import asyncio
import sqlite3
import random
import json
import yfinance as yf
from google import genai
from telegram import Bot
from dotenv import load_dotenv
from flow_god import analyze_with_ai_retry
from database import init_db, log_trade, get_performance_stats

load_dotenv()
init_db()

async def run_tilray_reconstruction():
    print("--- Recreating Tilray Insider Scenario Test ---")
    
    # 1. Exact Scenario Data
    ticker = "TLRY"
    trade_content = "🚨 UNUSUAL WHALES ALERT: TLRY $2.50 Calls expiring Jan 16. Massive 15,000 contract block trade detected. Size: $1.2M. Aggressive sweep above ask."
    
    # Context data reconstructed from research
    current_price = 1.95
    earnings_date = "2026-01-08"
    sec_context = (
        "Form 4 (2025-12-15): CEO Irwin D. Simon purchased 165,000 shares at $1.65.\n"
        "Form 4 (2025-12-18): CFO Carl A. Merton purchased 33,500 shares at $1.68.\n"
        "No major sales reported in the last 90 days."
    )
    news_context = (
        "Tilray Brands record international medical cannabis growth.\n"
        "Speculation on Project 420 cost-savings and US federal rescheduling.\n"
        "Analyst price targets raised ahead of January earnings."
    )
    
    print(f"🔹 Simulated Scenario: {ticker} (Earnings Jan 8)")
    print(f"🔹 Historical Insider Evidence: CEO/CFO heavy buying in Dec 2025")

    # 2. Test Gemini Analysis
    print("🔹 Testing Gemini 3 Flash Analysis on this scenario...")
    stats = get_performance_stats()
    
    data = await analyze_with_ai_retry(trade_content, news_context, stats, current_price, earnings_date, sec_context)
    
    if data and isinstance(data, dict):
        print(f"✅ JSON Parsed Successfully.")
        print(f"🔹 AI Conviction: {data.get('insider_conviction')}/10")
        print(f"🔹 AI Direction: {data.get('direction')}")
    else:
        print(f"❌ Gemini Analysis Failed")
        return

    # 3. Send to Telegram
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if tg_token and tg_chat_id:
        try:
            bot = Bot(token=tg_token)
            insider_tag = "🚨 <b>INSIDER ALERT</b>" if data['is_insider'] else "📊 <b>STANDARD FLOW</b>"
            final_msg = (
                f"🧪 <b>TILRAY RECONSTRUCTION TEST</b>\n"
                f"{insider_tag}\n"
                f"━━━━━━━━━━━━━━━━━\n"
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
            print("✅ Tilray Test Message Sent to Telegram")
        except Exception as e:
            print(f"❌ Telegram Failed: {e}")

    # 4. Cleanup (just in case)
    with sqlite3.connect('flow_god.db') as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE ticker = ?", (ticker,))
        conn.commit()

if __name__ == "__main__":
    asyncio.run(run_tilray_reconstruction())
