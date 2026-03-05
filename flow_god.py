import os
import random
import asyncio
import json
import discord
import yfinance as yf
from google import genai
from google.genai import types
from googlesearch import search
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
import re
from database import init_db, log_trade, get_performance_stats

load_dotenv()
init_db()

# Config
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEYS = [k.strip() for k in os.getenv('GEMINI_API_KEYS', '').split(',') if k.strip()]
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
PROCESSED_FILE = 'processed_messages.json'

STOP_WORDS = {"CALL", "PUT", "ALERT", "BUY", "SELL", "LONG", "SHORT", "ASK", "BID", "FLOW", "SIZE", "SWEEP", "BLOCK"}

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

async def get_macro_context():
    try:
        spy = yf.Ticker("SPY").history(period="2d")
        qqq = yf.Ticker("QQQ").history(period="2d")
        spy_ret = (spy['Close'].iloc[-1] / spy['Close'].iloc[-2] - 1) * 100
        qqq_ret = (qqq['Close'].iloc[-1] / qqq['Close'].iloc[-2] - 1) * 100
        return f"SPY: {spy_ret:+.2f}%, QQQ: {qqq_ret:+.2f}%"
    except: return "Macro data unavailable."

async def analyze_with_ai_retry(trade_content, news_context, stats, market_data):
    keys = list(GEMINI_API_KEYS)
    random.shuffle(keys)
    prompt = f"""
    Analyze this Unusual Whales trade report:
    {trade_content}

    QUANTITATIVE & OPTION DATA:
    {market_data}
    
    NEWS & FILINGS:
    {news_context}
    
    HISTORICAL PERFORMANCE:
    {stats}

    Return a JSON object:
    - is_insider: (boolean)
    - insider_conviction: (int 1-10)
    - is_golden_sweep: (boolean)
    - iv_warning: (string or null)
    - insider_logic: (HTML format)
    - meaningfulness: (string)
    - direction: (LONG/SHORT)
    - leverage: (int)
    - timeframe_hours: (int)
    - target_price: (float)
    - stop_loss: (float)
    - analysis: (Critical 4-5 sentence analysis in HTML format.)
    """
    for key in keys:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type='application/json')
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Key failed: {e}. Retrying...")
            await asyncio.sleep(5)
    return None

def fetch_news(ticker, query_type="general"):
    try:
        yesterday = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        query = f'site:sec.gov "{ticker}" ("Form 4" OR "13D" OR "13G") after:{yesterday}' if query_type == "sec" else f"{ticker} stock news insider catalyst after:{yesterday}"
        results = list(search(query, num_results=3, lang="en"))
        return "\n".join(results)
    except: return "No recent data found."

async def perform_full_analysis(trade_info, msg_time=None):
    """Core analysis logic reusable for Discord or Telegram."""
    match = re.search(r'\$([A-Z]{1,5})', trade_info)
    if not match: match = re.search(r'([A-Z]{1,5})\s+(?:Calls|Puts|\$)', trade_info)
    ticker = match.group(1) if match else "SPY"
            
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        hist_full = tk.history(period="1y")
        
        # Market Price at time of trade
        if msg_time:
            hist_1m = tk.history(start=msg_time - timedelta(minutes=5), end=msg_time + timedelta(minutes=5), interval="1m")
            entry_price = round(hist_1m['Close'].iloc[0], 2) if not hist_1m.empty else round(hist_full['Close'].iloc[-1], 2)
        else:
            entry_price = round(hist_full['Close'].iloc[-1], 2)

        mkt_cap = info.get('marketCap', 0)
        avg_vol = info.get('averageVolume', 1)
        
        # Technicals
        sma50 = round(hist_full['Close'].rolling(50).mean().iloc[-1], 2)
        rsi = round(calculate_rsi(hist_full['Close']).iloc[-1], 2)
        macro = await get_macro_context()

        market_data = (
            f"Ticker: {ticker} @ ${entry_price} | Market Cap: ${mkt_cap/1e9:.1f}B | ADV: {avg_vol:,}\n"
            f"Technicals: RSI={rsi}, 50SMA=${sma50}\n"
            f"Macro: {macro}\n"
            f"Earnings: {tk.calendar.get('Earnings Date', ['N/A'])[0] if isinstance(tk.calendar, dict) else 'N/A'}"
        )
        await asyncio.sleep(2)
    except:
        entry_price, market_data = 0, "Data fetch failed."

    news = fetch_news(ticker)
    sec = fetch_news(ticker, query_type="sec")
    stats = get_performance_stats()
    
    data = await analyze_with_ai_retry(trade_info, news + "\n" + sec, stats, market_data)
    if not data: return None, ticker, stats, entry_price

    if entry_price > 0:
        log_trade(ticker, data['direction'], data['leverage'], data['timeframe_hours'], 
                  data['insider_conviction'], entry_price, data['target_price'], data['stop_loss'])
    
    return data, ticker, stats, entry_price

def format_telegram_msg(ticker, data, stats, label="SIGNAL"):
    insider_tag = "🚨 <b>INSIDER ALERT</b>" if data['is_insider'] else "📊 <b>STANDARD FLOW</b>"
    golden_tag = "🏆 <b>GOLDEN SWEEP DETECTED</b>\n" if data.get('is_golden_sweep') else ""
    iv_box = f"⚠️ <b>{data['iv_warning']}</b>\n━━━━━━━━━━━━━━━━━\n" if data['iv_warning'] else ""
    
    return (
        f"🚀 <b>FLOWGOD {label}: {ticker}</b>\n"
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

async def handle_telegram_inbound(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle copy-pasted alerts in Telegram."""
    if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID): return
    
    text = update.message.text
    status_msg = await update.message.reply_text("🧠 <b>FlowGod is analyzing...</b>", parse_mode='HTML')
    
    data, ticker, stats, entry_price = await perform_full_analysis(text)
    
    if data:
        final_msg = format_telegram_msg(ticker, data, stats, label="REQUEST")
        await update.message.reply_text(final_msg, parse_mode='HTML')
    else:
        await update.message.reply_text("❌ Analysis failed. Check Gemini API keys.")
    
    await status_msg.delete()

async def main():
    if not TELEGRAM_TOKEN: return
    
    # Start Telegram Listener in background
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_telegram_inbound))
    
    print("🚀 FlowGod is now listening for Telegram requests...")
    # Run the bot polling in a separate task
    asyncio.create_task(app.run_polling())

    # Keep the script alive for Discord monitoring too (if ever enabled)
    if DISCORD_TOKEN:
        client = discord.Client(intents=discord.Intents.default())
        @client.event
        async def on_ready():
            print(f"Logged in as {client.user} (Passive Monitor)")
        
        # Note: run_polling is non-blocking when used this way
        await client.start(DISCORD_TOKEN)
    else:
        # If no Discord token, just hang the main loop
        while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
