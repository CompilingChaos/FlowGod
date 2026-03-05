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
from database import init_db, log_trade, get_performance_stats, log_long_term_flow, get_daily_trends, log_report, get_last_week_reports, clear_daily_flow

load_dotenv()
init_db()

# Config
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEYS = [k.strip() for k in os.getenv('GEMINI_API_KEYS', '').split(',') if k.strip()]
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
PROCESSED_FILE = 'processed_messages.json'

STOP_WORDS = {"CALL", "PUT", "ALERT", "BUY", "SELL", "LONG", "SHORT", "ASK", "BID", "FLOW", "SIZE", "SWEEP", "BLOCK"}

def parse_premium(prem_str):
    """Convert premium string like $255,500 or $1.2M to float."""
    if not prem_str: return 0
    val = str(prem_str).replace('$', '').replace(',', '').strip()
    multiplier = 1
    if 'K' in val.upper():
        multiplier = 1000
        val = val.upper().replace('K', '')
    elif 'M' in val.upper():
        multiplier = 1000000
        val = val.upper().replace('M', '')
    elif 'B' in val.upper():
        multiplier = 1000000000
        val = val.upper().replace('B', '')
    try:
        return float(val) * multiplier
    except:
        return 0

def is_long_term(expiry_str):
    """Check if expiry is more than 30 days away."""
    if not expiry_str or expiry_str == "N/A": return False
    try:
        exp_date = datetime.strptime(expiry_str, '%m/%d/%Y')
        return (exp_date - datetime.now()).days > 30
    except:
        try:
            exp_date = datetime.strptime(expiry_str, '%Y-%m-%d')
            return (exp_date - datetime.now()).days > 30
        except:
            return False

async def send_daily_trends():
    """Compile, summarize with AI, and send daily smart money trends to Telegram."""
    trends = get_daily_trends()
    if not trends: return
    
    past_reports = get_last_week_reports()
    
    # Format today's raw data for the AI
    raw_data = "\n".join([f"{t}: {d}, ${p/1e6:.1f}M ({c} orders)" for t, d, p, c in trends])
    
    history_context = "\n---\n".join(past_reports) if past_reports else "No historical reports available."
    
    prompt = f"""
    You are the FlowGod institutional analyst. Summarize today's Smart Money Trends based on long-term institutional option flow (>30 DTE).
    
    TODAY'S RAW DATA:
    {raw_data}
    
    PAST WEEK'S SUMMARIES FOR CONTEXT:
    {history_context}
    
    INSTRUCTIONS:
    1. Identify the top 3 high-conviction institutional themes today.
    2. Note if any tickers from the past week are seeing REPEAT buying/selling (this is critical).
    3. Keep it professional, data-driven, and concise.
    4. Format in clean HTML for Telegram.
    5. End with a "Market Sentiment" score (1-10) based on this long-term flow.
    """
    
    summary = "Unable to generate summary."
    keys = list(GEMINI_API_KEYS)
    random.shuffle(keys)
    
    for key in keys:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt
            )
            summary = response.text
            break
        except Exception as e:
            print(f"Daily summary key failed: {e}")

    # Log the report for future context
    log_report(summary)
    
    # Send to Telegram
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"📊 <b>END-OF-DAY INSTITUTIONAL INTELLIGENCE</b>\n\n{summary}", parse_mode='HTML')
    
    # Clear today's bucket for a fresh start tomorrow
    clear_daily_flow()
    print("🧹 Daily flow cleared and report archived.")

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

def get_content_hash(text):
    """Generate a unique hash for message content."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

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
                model='gemini-2.0-flash',
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
    match = re.search(r'\$([A-Z]{1,5})', trade_info)
    if not match: match = re.search(r'([A-Z]{1,5})\s+(?:Calls|Puts|\$)', trade_info)
    
    ts_match = re.search(r'^([A-Z]{1,5})\s+([\d\.]+)\s+([CP])\s+([\d\/]{8,10})', trade_info, re.M)
    
    if ts_match:
        ticker = ts_match.group(1).upper()
        strike_val = ts_match.group(2)
        option_type = "Calls" if ts_match.group(3) == "C" else "Puts"
        expiry_val = ts_match.group(4)
    else:
        ticker = match.group(1).upper() if match else "SPY"
        strike_val = "N/A"
        expiry_val = "N/A"
        option_type = "Options"

    # Extract metrics
    prem_match = re.search(r'Prem(?:ium)?:\s*\$([\d\.,]+[KMB]?)', trade_info, re.I)
    premium_raw = prem_match.group(1) if prem_match else "0"
    premium_usd = parse_premium(premium_raw)
    
    # --- FILTER 1: PREMIUM FLOOR ($100k) ---
    if premium_usd < 100000:
        print(f"⏩ Skipping {ticker}: Premium ${premium_usd:,.0f} below $100k floor.")
        return None, ticker, None, 0

    # --- FILTER 2: LONG-TERM STORAGE (>30 Days) ---
    if is_long_term(expiry_val):
        print(f"📦 Storing {ticker} in Long-Term DB (Expiry: {expiry_val})")
        v_match = re.search(r'Vol/OI:\s*([\d\.]+)', trade_info, re.I)
        o_match = re.search(r'OTM:\s*([-\d\.\%]+)', trade_info, re.I)
        b_match = re.search(r'Bid/Ask %:\s*([\d\/]+)', trade_info, re.I)
        
        log_long_term_flow(ticker, option_type, strike_val, expiry_val, premium_usd, 
                          float(v_match.group(1)) if v_match else 0, 
                          float(o_match.group(1).replace('%','')) if o_match else 0, 
                          b_match.group(1) if b_match else "N/A")
        return "STORED", ticker, None, 0

    v_val = re.search(r'Vol/OI:\s*([\d\.]+)', trade_info, re.I)
    o_val = re.search(r'OTM:\s*([-\d\.\%]+)', trade_info, re.I)
    b_val = re.search(r'Bid/Ask %:\s*([\d\/]+)', trade_info, re.I)
    m_val = re.search(r'Multi-leg Volume:\s*([\d\%]+)', trade_info, re.I)
    
    print(f"🔥 Analyzing Hot Flow: {ticker} {option_type} (${premium_usd:,.0f})")

    try:
        tk = yf.Ticker(ticker)
        try:
            info = tk.info
        except Exception:
            info = {}

        hist_full = tk.history(period="1y")
        if msg_time:
            hist_1m = tk.history(start=msg_time - timedelta(minutes=5), end=msg_time + timedelta(minutes=5), interval="1m")
            entry_price = round(hist_1m['Close'].iloc[0], 2) if not hist_1m.empty else round(hist_full['Close'].iloc[-1], 2)
        else:
            entry_price = round(hist_full['Close'].iloc[-1], 2)

        mkt_cap = info.get('marketCap') or info.get('totalAssets', 0)
        sma50 = round(hist_full['Close'].rolling(50).mean().iloc[-1], 2) if not hist_full.empty else 0
        rsi = round(calculate_rsi(hist_full['Close']).iloc[-1], 2) if not hist_full.empty else 0
        macro = await get_macro_context()

        market_data = (
            f"Ticker: {ticker} @ ${entry_price} | Size: {mkt_cap/1e9:.1f}B\n"
            f"Option: {strike_val} {option_type} Exp {expiry_val}\n"
            f"Metrics: Vol/OI={v_val.group(1) if v_val else 'N/A'} | OTM={o_val.group(1) if o_val else 'N/A'} | Bid/Ask={b_val.group(1) if b_val else 'N/A'}\n"
            f"Complexity: Multi-leg={m_val.group(1) if m_val else '0%'}\n"
            f"Technicals: RSI={rsi}, 50SMA=${sma50} | Macro: {macro}\n"
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

    processed = []
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f: processed = json.load(f)

    for msg in scraped:
        content = msg['content']
        if content in processed: continue
        
        print(f"🐋 Processing Scraped Alert: {content[:50]}...")
        data, ticker, stats, entry_price = await perform_full_analysis(content)
        
        if data:
            if data != "STORED": # Don't send telegram for long-term stored flow
                final_msg = format_telegram_msg(ticker, data, stats, label="AUTOPILOT")
                bot = Bot(token=TELEGRAM_TOKEN)
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=final_msg, parse_mode='HTML')
            
            processed.append(content)
            if len(processed) > 500: processed.pop(0)

    with open(PROCESSED_FILE, 'w') as f: json.dump(processed, f)

async def main():
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN is missing!")
        return
    
    if os.path.exists('unusual_messages.json'):
        await process_scraped_messages()
        current_hour = datetime.now().hour
        if current_hour >= 21:
            await send_daily_trends()
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_telegram_inbound))
    
    print("🚀 FlowGod is now listening for Telegram requests...")
    asyncio.create_task(app.run_polling())

    if DISCORD_TOKEN:
        client = discord.Client(intents=discord.Intents.default())
        @client.event
        async def on_ready():
            print(f"Logged in as {client.user} (Passive Monitor)")
        await client.start(DISCORD_TOKEN)
    else:
        while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
