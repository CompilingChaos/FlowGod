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
    # --- DEEP EXTRACTION PARSER (UPDATED FOR TIME & SALES) ---
    # Try the standard format first
    match = re.search(r'\$([A-Z]{1,5})', trade_info)
    if not match: match = re.search(r'([A-Z]{1,5})\s+(?:Calls|Puts|\$)', trade_info)
    
    # Try the "Time & Sales" format: TICKER STRIKE C/P EXPIRY
    # Example: MRVL 80 C 03/06/2026
    ts_match = re.search(r'^([A-Z]{1,5})\s+([\d\.]+)\s+([CP])\s+([\d\/]{8,10})', trade_info, re.M)
    
    if ts_match:
        ticker = ts_match.group(1)
        strike_val = ts_match.group(2)
        option_type = "Calls" if ts_match.group(3) == "C" else "Puts"
        expiry_val = ts_match.group(4)
    else:
        ticker = match.group(1) if match else "SPY"
        strike_val = "N/A"
        expiry_val = "N/A"
        option_type = "Options"

    # Extract additional metrics
    premium = re.search(r'Prem(?:ium)?:\s*\$([\d\.,]+[KMB]?)', trade_info, re.I)
    vol_oi = re.search(r'Vol/OI:\s*([\d\.]+)', trade_info, re.I)
    
    ticker = ticker.upper()
    print(f"🔍 Analyzing {ticker} {option_type} (Prem: {premium.group(1) if premium else 'N/A'} | Vol/OI: {vol_oi.group(1) if vol_oi else 'N/A'})")

    try:
        tk = yf.Ticker(ticker)
        
        # --- ETF-AWARE LOGIC ---
        # info.get() can trigger a 404 for ETFs if we access certain keys
        try:
            info = tk.info
        except Exception:
            info = {} # Fallback for ETFs or API errors

        hist_full = tk.history(period="1y")
        
        # Market Price at time of trade
        if msg_time:
            hist_1m = tk.history(start=msg_time - timedelta(minutes=5), end=msg_time + timedelta(minutes=5), interval="1m")
            entry_price = round(hist_1m['Close'].iloc[0], 2) if not hist_1m.empty else round(hist_full['Close'].iloc[-1], 2)
        else:
            entry_price = round(hist_full['Close'].iloc[-1], 2)

        # Handling ETFs differently (they use totalAssets instead of marketCap)
        mkt_cap = info.get('marketCap') or info.get('totalAssets', 0)
        avg_vol = info.get('averageVolume', 1)
        
        # Technicals
        sma50 = round(hist_full['Close'].rolling(50).mean().iloc[-1], 2) if not hist_full.empty else 0
        rsi = round(calculate_rsi(hist_full['Close']).iloc[-1], 2) if not hist_full.empty else 0
        macro = await get_macro_context()

        market_data = (
            f"Ticker: {ticker} @ ${entry_price} | Size: {mkt_cap/1e9:.1f}B | ADV: {avg_vol:,}\n"
            f"Strike: {strike.group(1) if strike else 'N/A'} | Expiry: {expiry.group(1) if expiry else 'N/A'}\n"
            f"Technicals: RSI={rsi}, 50SMA=${sma50}\n"
            f"Macro: {macro}\n"
            f"Earnings: {tk.calendar.get('Earnings Date', ['N/A'])[0] if isinstance(tk.calendar, dict) else 'N/A'}"
        )
        await asyncio.sleep(2)
    except Exception as e:
        print(f"⚠️ YFinance error for {ticker}: {e}")
        entry_price, market_data = 0, f"Data fetch failed for {ticker}."

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

async def process_scraped_messages():
    """Read unusual_messages.json and process any new ones."""
    if not os.path.exists('unusual_messages.json'): return
    
    try:
        with open('unusual_messages.json', 'r') as f:
            scraped = json.load(f)
    except: return

    # Load processed state
    processed = []
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f: processed = json.load(f)

    for msg in scraped:
        content = msg['content']
        # Simple deduplication based on content (could be improved with hashes)
        if content in processed: continue
        
        print(f"🐋 Processing Scraped Alert: {content[:50]}...")
        data, ticker, stats, entry_price = await perform_full_analysis(content)
        
        if data:
            final_msg = format_telegram_msg(ticker, data, stats, label="AUTOPILOT")
            bot = Bot(token=TELEGRAM_TOKEN)
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=final_msg, parse_mode='HTML')
            
            processed.append(content)
            # Keep log manageable (last 500)
            if len(processed) > 500: processed.pop(0)

    with open(PROCESSED_FILE, 'w') as f: json.dump(processed, f)

async def main():
    # If no TELEGRAM_TOKEN, the whole system breaks.
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN is missing!")
        return
    
    # Mode 1: Processing Scraped Messages (for GitHub Actions)
    if os.path.exists('unusual_messages.json'):
        await process_scraped_messages()
        return

    # Mode 2: Interactive Telegram Listener (for local run)
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
