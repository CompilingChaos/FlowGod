import os
import random
import asyncio
import json
import discord
import yfinance as yf
from google import genai
from google.genai import types
from googlesearch import search
from telegram import Bot
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

tg_bot = Bot(token=TELEGRAM_TOKEN)

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
    except:
        return "Macro data unavailable."

async def analyze_with_ai_retry(trade_content, news_context, stats, market_data):
    """Randomly selects keys and enforces strict JSON output with Macro/TA/IV context."""
    keys = list(GEMINI_API_KEYS)
    random.shuffle(keys)
    
    prompt = f"""
    Analyze this Unusual Whales trade report:
    {trade_content}

    QUANTITATIVE DATA:
    {market_data}
    
    NEWS & FILINGS:
    {news_context}
    
    HISTORICAL PERFORMANCE:
    {stats}

    Task:
    Provide a CRITICAL analysis. 
    - Check for "IV Crush" risk (flag if IV is exceptionally high relative to history).
    - Align trade with Macro (SPY/QQQ) and Technicals (RSI/SMAs).
    
    Return a JSON object with exactly these keys:
    - is_insider: (boolean)
    - insider_conviction: (int 1-10)
    - iv_warning: (string or null, e.g. "HIGH IV RISK" or null if safe)
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
        query = f"site:sec.gov {ticker} filing after:{yesterday}" if query_type == "sec" else f"{ticker} stock news insider after:{yesterday}"
        results = list(search(query, num_results=3, lang="en"))
        return "\n".join(results)
    except: return "No recent data found."

async def process_message(message):
    trade_info = f"Author: {message.author}\nContent: {message.content}\n"
    if message.embeds:
        for e in message.embeds: trade_info += f"Embed: {e.title} - {e.description}\n"
    
    ticker = "SPY" 
    words = trade_info.replace('$', '').split()
    for word in words:
        if word.isupper() and 1 < len(word) < 6:
            ticker = word
            break
            
    # Fetch Complex Market Data
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1y")
        curr = hist.iloc[-1]
        
        entry_price = round(curr['Close'], 2)
        sma50 = round(hist['Close'].rolling(50).mean().iloc[-1], 2)
        sma200 = round(hist['Close'].rolling(200).mean().iloc[-1], 2)
        rsi = round(calculate_rsi(hist['Close']).iloc[-1], 2)
        
        # IV Proxy (simplified for free data)
        iv_proxy = round(tk.options[0] if tk.options else 0, 2) # Just a placeholder for raw options availability
        macro = await get_macro_context()
        
        market_data = (
            f"Ticker: {ticker} @ ${entry_price}\n"
            f"Technicals: RSI={rsi}, 50SMA=${sma50}, 200SMA=${sma200}\n"
            f"Macro: {macro}\n"
            f"Earnings: {tk.calendar.get('Earnings Date', ['N/A'])[0] if isinstance(tk.calendar, dict) else 'N/A'}"
        )
        await asyncio.sleep(3)
    except:
        entry_price, market_data = 0, "Data fetch failed."

    news = fetch_news(ticker)
    sec = fetch_news(ticker, query_type="sec")
    stats = get_performance_stats()
    
    data = await analyze_with_ai_retry(trade_info, news + "\n" + sec, stats, market_data)
    if not data: return

    if entry_price > 0:
        log_trade(ticker, data['direction'], data['leverage'], data['timeframe_hours'], 
                  data['insider_conviction'], entry_price, data['target_price'], data['stop_loss'])

    # Build High-Quality Telegram Message
    insider_tag = "🚨 <b>INSIDER ALERT</b>" if data['is_insider'] else "📊 <b>STANDARD FLOW</b>"
    iv_box = f"⚠️ <b>{data['iv_warning']}</b>\n━━━━━━━━━━━━━━━━━\n" if data['iv_warning'] else ""
    
    final_msg = (
        f"🚀 <b>FLOWGOD SIGNAL: {ticker}</b>\n"
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

    try:
        await tg_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=final_msg, parse_mode='HTML')
    except Exception as e: print(f"Telegram error: {e}")

async def main():
    if not DISCORD_TOKEN or not GEMINI_API_KEYS: return
    client = discord.Client(intents=discord.Intents.default())
    @client.event
    async def on_ready():
        if os.path.exists(PROCESSED_FILE):
            with open(PROCESSED_FILE, 'r') as f: processed = json.load(f)
        else: processed = []
        new_processed = []
        for guild in client.guilds:
            for channel in guild.text_channels:
                if any(k in channel.name.lower() for k in ["unusual", "whale", "flow"]):
                    async for message in channel.history(limit=10):
                        if message.id not in processed:
                            await process_message(message)
                            new_processed.append(message.id)
        with open(PROCESSED_FILE, 'w') as f: json.dump(processed + new_processed, f)
        await client.close()
    await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
