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
    print("--- Recreating Tilray Insider Scenario (Advanced Mode) ---")
    
    # 1. Exact Scenario Data
    ticker = "TLRY"
    trade_content = "🚨 UNUSUAL WHALES ALERT: TLRY $2.50 Calls expiring Jan 16. Massive 15,000 contract block trade detected. Size: $1.2M. Aggressive sweep above ask."
    
    # Reconstructed Context
    news_sec_context = (
        "Form 4 (Dec 2025): CEO purchased 165k shares @ $1.65. CFO purchased 33k shares @ $1.68.\n"
        "News: Tilray record international medical cannabis growth. Speculation on Project 420 savings."
    )
    
    # 2. Simulated Market Data (Recreating Jan 2026 conditions)
    market_data = (
        "Ticker: TLRY @ $1.95\n"
        "Technicals: RSI=58 (Neutral), 50SMA=$1.72, 200SMA=$1.85 (Price above all SMAs)\n"
        "Macro: SPY: +0.45%, QQQ: +0.60% (Bullish Market Trend)\n"
        "Earnings: 2026-01-08"
    )
    
    print(f"🔹 Simulated Scenario: {ticker} (Pre-Earnings Jan 2026)")

    # 3. Test Gemini Analysis (Insider + Quantitative)
    print("🔹 Testing Gemini 3 Flash (Advanced Critical Analysis)...")
    stats = get_performance_stats()
    data = await analyze_with_ai_retry(trade_content, news_sec_context, stats, market_data)
    
    if data and isinstance(data, dict):
        print(f"✅ JSON Parsed. Insider Conviction: {data.get('insider_conviction')}/10")
    else:
        print(f"❌ Gemini Analysis Failed")
        return

    # 4. Test Telegram Notification (Advanced UI)
    print("🔹 Sending Advanced Signal to Telegram...")
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if tg_token and tg_chat_id:
        try:
            bot = Bot(token=tg_token)
            insider_tag = "🚨 <b>INSIDER ALERT</b>" if data['is_insider'] else "📊 <b>STANDARD FLOW</b>"
            iv_box = f"⚠️ <b>{data['iv_warning']}</b>\n━━━━━━━━━━━━━━━━━\n" if data['iv_warning'] else ""
            
            final_msg = (
                f"🧪 <b>TILRAY ADVANCED RECONSTRUCTION</b>\n"
                f"{insider_tag}\n"
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
            print("✅ Tilray Advanced Message Sent")
        except Exception as e:
            print(f"❌ Telegram Failed: {e}")

    # 5. Cleanup
    with sqlite3.connect('flow_god.db') as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE ticker = ?", (ticker,))
        conn.commit()
    print("✅ Cleanup Complete")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())
