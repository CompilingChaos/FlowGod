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

async def run_tilray_2024_reconstruction():
    print("--- Recreating Tilray 2024 Earnings Beat Scenario ---")
    
    # 1. Exact Historical Scenario Data (Jan 2024)
    ticker = "TLRY"
    trade_content = (
        "🚨 UNUSUAL WHALES ALERT: TLRY $2.00 Calls expiring Jan 19. "
        "Block trade of 25,000 contracts detected. Size: $2.1M. "
        "Sweep executed at the ASK during high-volume breakout."
    )
    
    # Reconstructed Insider/News Context
    news_sec_context = (
        "Earnings: Double Beat reported Jan 9 (Record $194M Revenue, $0.00 Adj EPS).\n"
        "Insider: CFO Carl Merton purchased shares at $1.80 leading into the report.\n"
        "News: Successful diversification into craft beer; reduction in convertible debt."
    )
    
    # 2. Simulated Market Data (Recreating the high-momentum timing)
    market_data = (
        "Ticker: TLRY @ $1.82 (Pre-Jump)\n"
        "Technicals: RSI=62 (Strong Momentum), 50SMA=$1.65, 200SMA=$1.75 (Golden Cross forming)\n"
        "Macro: SPY: +0.85%, QQQ: +1.10% (Growth Stock Rally)\n"
        "Earnings: 2024-01-09 (Double Beat Potential)"
    )
    
    print(f"🔹 Simulated Scenario: {ticker} (Jan 2024 Momentum Play)")

    # 3. Test Gemini Analysis
    print("🔹 Testing Gemini 3 Flash (High-Conviction Reconstruction)...")
    stats = get_performance_stats()
    data = await analyze_with_ai_retry(trade_content, news_sec_context, stats, market_data)
    
    if data and isinstance(data, dict):
        print(f"✅ JSON Parsed. Insider Logic: {data.get('insider_logic')[:50]}...")
    else:
        print(f"❌ Gemini Analysis Failed")
        return

    # 4. Send to Telegram
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if tg_token and tg_chat_id:
        try:
            bot = Bot(token=tg_token)
            insider_tag = "🚨 <b>INSIDER ALERT</b>" if data['is_insider'] else "📊 <b>STANDARD FLOW</b>"
            iv_box = f"⚠️ <b>{data['iv_warning']}</b>\n━━━━━━━━━━━━━━━━━\n" if data['iv_warning'] else ""
            
            final_msg = (
                f"🧪 <b>TILRAY 2024 RECONSTRUCTION</b>\n"
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
            print("✅ Tilray 2024 Reconstruction Sent")
        except Exception as e:
            print(f"❌ Telegram Failed: {e}")

    # 5. Cleanup
    with sqlite3.connect('flow_god.db') as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE ticker = ?", (ticker,))
        conn.commit()

if __name__ == "__main__":
    asyncio.run(run_tilray_2024_reconstruction())
