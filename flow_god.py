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

    Task:
    Provide a CRITICAL analysis. 
    - Identify if this is a "GOLDEN SWEEP" (Volume > Open Interest).
    - Evaluate trade size significance relative to Market Cap and ADV.
    - Check for IV Crush and technical alignment.
    
    Return a JSON object with exactly these keys:
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

async def process_message(message):
    trade_info = f"Author: {message.author}\nContent: {message.content}\n"
    if message.embeds:
        for e in message.embeds: trade_info += f"Embed: {e.title} - {e.description}\n"
    
    # Ticker Extraction
    match = re.search(r'\$([A-Z]{1,5})', trade_info)
    if not match: match = re.search(r'([A-Z]{1,5})\s+(?:Calls|Puts|\$)', trade_info)
    ticker = match.group(1) if match else "SPY"
            
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        hist_full = tk.history(period="1y")
        
        # 1. Market Cap & ADV
        mkt_cap = info.get('marketCap', 0)
        avg_vol = info.get('averageVolume', 1)
        
        # 2. Extract Option details (Strike/Expiry/Type) from text
        # Example: "$250 Calls expiring Jan 16"
        strike_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*(?:Call|Put)', trade_info, re.I)
        type_match = re.search(r'(Call|Put)s?', trade_info, re.I)
        vol_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*contracts', trade_info, re.I)
        
        option_context = "Option Data: "
        if strike_match and type_match and tk.options:
            target_strike = float(strike_match.group(1))
            opt_type = type_match.group(1).upper()
            trade_vol = int(vol_match.group(1).replace(',', '')) if vol_match else 0
            
            # Use first available expiry as proxy if none parsed
            chain = tk.option_chain(tk.options[0])
            opts = chain.calls if "CALL" in opt_type else chain.puts
            # Find specific strike
            row = opts[opts['strike'] == target_strike]
            if not row.empty:
                oi = row['openInterest'].iloc[0]
                iv = row['impliedVolatility'].iloc[0] * 100
                is_golden = trade_vol > oi if oi > 0 else False
                option_context += f"Strike ${target_strike} {opt_type}, OI: {oi}, IV: {iv:.1f}%, Volume: {trade_vol} {'(GOLDEN SWEEP!)' if is_golden else ''}"
            else: option_context += "Strike not found in front-month."
        else: option_context += "Could not parse option specifics."

        # Technicals & Macro
        entry_price = round(hist_full['Close'].iloc[-1], 2)
        sma50 = round(hist_full['Close'].rolling(50).mean().iloc[-1], 2)
        rsi = round(calculate_rsi(hist_full['Close']).iloc[-1], 2)
        macro = await get_macro_context()

        market_data = (
            f"Ticker: {ticker} @ ${entry_price} | Market Cap: ${mkt_cap/1e9:.1f}B | ADV: {avg_vol:,}\n"
            f"Technicals: RSI={rsi}, 50SMA=${sma50}\n"
            f"{option_context}\n"
            f"Macro: {macro}\n"
            f"Earnings: {tk.calendar.get('Earnings Date', ['N/A'])[0] if isinstance(tk.calendar, dict) else 'N/A'}"
        )
        await asyncio.sleep(3)
    except Exception as e:
        entry_price, market_data = 0, f"Data fetch failed: {e}"

    news = fetch_news(ticker)
    sec = fetch_news(ticker, query_type="sec")
    stats = get_performance_stats()
    
    data = await analyze_with_ai_retry(trade_info, news + "\n" + sec, stats, market_data)
    if not data: return

    if entry_price > 0:
        log_trade(ticker, data['direction'], data['leverage'], data['timeframe_hours'], 
                  data['insider_conviction'], entry_price, data['target_price'], data['stop_loss'])

    # Build Advanced Telegram Message
    insider_tag = "🚨 <b>INSIDER ALERT</b>" if data['is_insider'] else "📊 <b>STANDARD FLOW</b>"
    golden_tag = "🏆 <b>GOLDEN SWEEP DETECTED</b>\n" if data.get('is_golden_sweep') else ""
    iv_box = f"⚠️ <b>{data['iv_warning']}</b>\n━━━━━━━━━━━━━━━━━\n" if data['iv_warning'] else ""
    
    final_msg = (
        f"🚀 <b>FLOWGOD SIGNAL: {ticker}</b>\n"
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
