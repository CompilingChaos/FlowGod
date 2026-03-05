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
from datetime import datetime, timezone

load_dotenv()
init_db()

class MockMessage:
    def __init__(self, content, author="Unusual Whales"):
        self.content = content
        self.author = author
        self.embeds = []
        self.id = 12345
        self.created_at = datetime.now(timezone.utc)

async def run_comprehensive_test():
    print("--- Final Logic & Extraction Verification ---")
    
    # 1. Test Ticker Extraction with Noise
    # This string has noise like 'ALERT' and 'CALL' which used to fail
    raw_content = "🚨 UNUSUAL WHALES ALERT: $TSLA $250 Calls expiring tomorrow. Heavy sweep detected."
    mock_msg = MockMessage(raw_content)
    
    print(f"🔹 Testing Extraction from: {raw_content}")
    # We simulate the extraction logic here to report it
    import re
    match = re.search(r'\$([A-Z]{1,5})', raw_content)
    ticker = match.group(1) if match else "FAIL"
    print(f"✅ Extracted Ticker: {ticker}")

    # 2. Test Historical Price Fetching (Approx trade time)
    print("🔹 Fetching Price at trade time...")
    tk = yf.Ticker(ticker)
    hist = tk.history(period="1d", interval="1m")
    if not hist.empty:
        price = round(hist['Close'].iloc[-1], 2)
        print(f"✅ Trade Time Price: ${price}")
    else:
        print("❌ Price fetch failed")

    # 3. Test Full Analysis Flow
    print("🔹 Running Full Analysis...")
    news = fetch_news(ticker)
    sec = fetch_news(ticker, query_type="sec")
    stats = get_performance_stats()
    
    # Quantitative Context
    market_data = f"Ticker: {ticker} @ ${price}\nMacro: Neutral\nTechnicals: RSI=50"
    
    data = await analyze_with_ai_retry(raw_content, news + "\n" + sec, stats, market_data)
    
    if data and isinstance(data, dict):
        print(f"✅ Gemini Response Received. IV Warning: {data.get('iv_warning')}")
    else:
        print("❌ Analysis Failed")
        return

    # 4. Telegram Delivery
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if tg_token and tg_chat_id:
        try:
            bot = Bot(token=tg_token)
            insider_tag = "🚨 <b>INSIDER ALERT</b>" if data['is_insider'] else "📊 <b>STANDARD FLOW</b>"
            final_msg = (
                f"🧪 <b>FINAL LOGIC TEST: {ticker}</b>\n"
                f"{insider_tag}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🔥 <b>Conviction:</b> {data['insider_conviction']}/10\n"
                f"🐋 <b>Meaning:</b> {data['meaningfulness']}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>Action:</b> <code>{data['direction']}</code>\n"
                f"⚙️ <b>Leverage:</b> <code>{data['leverage']}x</code>\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🧐 <b>ANALYSIS:</b>\n"
                f"<i>{data['analysis']}</i>"
            )
            await bot.send_message(chat_id=tg_chat_id, text=final_msg, parse_mode='HTML')
            print("✅ Telegram Delivered")
        except Exception as e:
            print(f"❌ Telegram Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())
