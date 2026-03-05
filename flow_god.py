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
import hashlib
from database import init_db, log_trade, get_performance_stats, log_long_term_flow, get_daily_trends, log_report, get_last_week_reports, clear_daily_flow, get_ticker_daily_stats

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

def calculate_iv_rank(ticker):
    """Approximate IV Rank using historical price volatility as a proxy."""
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1y")
        if hist.empty: return 0
        hist['returns'] = hist['Close'].pct_change()
        hist['vol'] = hist['returns'].rolling(window=30).std() * (252**0.5)
        current_vol = hist['vol'].iloc[-1]
        min_vol = hist['vol'].min()
        max_vol = hist['vol'].max()
        if max_vol == min_vol: return 50
        iv_rank = ((current_vol - min_vol) / (max_vol - min_vol)) * 100
        return round(iv_rank, 2)
    except: return 0

async def send_daily_trends():
    """Compile, summarize with AI, and send daily smart money trends to Telegram."""
    trends = get_daily_trends()
    if not trends: return
    past_reports = get_last_week_reports()
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
    2. Note if any tickers from the past week are seeing REPEAT buying/selling.
    3. Format in clean HTML for Telegram.
    4. End with a "Market Sentiment" score (1-10).
    """
    summary = "Unable to generate summary."
    keys = list(GEMINI_API_KEYS)
    random.shuffle(keys)
    for key in keys:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(model='gemini-3-flash-preview', contents=prompt)
            summary = response.text
            break
        except: continue
    log_report(summary)
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"📊 <b>END-OF-DAY INSTITUTIONAL INTELLIGENCE</b>\n\n{summary}", parse_mode='HTML')
    clear_daily_flow()

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

async def analyze_with_ai_retry(trade_content, news_context, stats, market_data, daily_context):
    keys = list(GEMINI_API_KEYS)
    random.shuffle(keys)
    prompt = f"""
    Analyze this Unusual Whales trade report:
    {trade_content}
    QUANTITATIVE & OPTION DATA:
    {market_data}
    CUMULATIVE DAILY CONTEXT FOR THIS TICKER:
    {daily_context}
    NEWS & FILINGS:
    {news_context}
    HISTORICAL PERFORMANCE:
    {stats}
    Return a JSON object with: is_insider, insider_conviction (1-10), is_golden_sweep, iv_warning, insider_logic (HTML), meaningfulness, direction (LONG/SHORT), leverage, timeframe_hours, target_price, stop_loss, analysis (HTML).
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
            await asyncio.sleep(2)
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
    ts_match = re.search(r'^([A-Z]{1,5})\s+([\d\.]+)\s+([CP])\s+([\d\/]{8,10})', trade_info, re.M)
    if ts_match:
        ticker = ts_match.group(1).upper()
        strike_val = ts_match.group(2)
        option_type = "Calls" if ts_match.group(3) == "C" else "Puts"
        expiry_val = ts_match.group(4)
    else:
        ticker = match.group(1).upper() if match else "SPY"
        strike_val, expiry_val, option_type = "N/A", "N/A", "Options"
    prem_match = re.search(r'Prem(?:ium)?:\s*\$([\d\.,]+[KMB]?)', trade_info, re.I)
    premium_usd = parse_premium(prem_match.group(1) if prem_match else "0")
    if premium_usd < 100000: return None, ticker, None, 0
    if is_long_term(expiry_val):
        v_match = re.search(r'Vol/OI:\s*([\d\.]+)', trade_info, re.I)
        o_match = re.search(r'OTM:\s*([-\d\.\%]+)', trade_info, re.I)
        b_match = re.search(r'Bid/Ask %:\s*([\d\/]+)', trade_info, re.I)
        log_long_term_flow(ticker, option_type, strike_val, expiry_val, premium_usd, 
                          float(v_match.group(1)) if v_match else 0, 
                          float(o_match.group(1).replace('%','')) if o_match else 0, 
                          b_match.group(1) if b_match else "N/A")
        return "STORED", ticker, None, 0
    iv_rank = calculate_iv_rank(ticker)
    try:
        tk = yf.Ticker(ticker)
        hist_full = tk.history(period="1y")
        entry_price = round(hist_full['Close'].iloc[-1], 2)
        mkt_cap = (tk.info.get('marketCap') or tk.info.get('totalAssets', 0)) if tk.info else 0
        sma50 = round(hist_full['Close'].rolling(50).mean().iloc[-1], 2)
        rsi = round(calculate_rsi(hist_full['Close']).iloc[-1], 2)
        macro = await get_macro_context()
        market_data = (f"Ticker: {ticker} @ ${entry_price} | Size: {mkt_cap/1e9:.1f}B | IV Rank: {iv_rank}%\n"
                      f"Option: {strike_val} {option_type} Exp {expiry_val}\n"
                      f"Metrics: RSI={rsi}, 50SMA=${sma50} | Macro: {macro}")
    except:
        entry_price, market_data = 0, "Data fetch failed."
    news = fetch_news(ticker); sec = fetch_news(ticker, query_type="sec"); stats = get_performance_stats()
    d_stats = get_ticker_daily_stats(ticker)
    daily_context = f"This day there have been {d_stats['CALL']['count']} call alerts with a total premium of ${d_stats['CALL']['prem']/1e3:.0f}k and {d_stats['PUT']['count']} puts with a premium of ${d_stats['PUT']['prem']/1e3:.0f}k."
    data = await analyze_with_ai_retry(trade_info, news + "\n" + sec, stats, market_data, daily_context)
    if not data: return None, ticker, stats, entry_price
    if entry_price > 0:
        log_trade(ticker, data['direction'], data['leverage'], data['timeframe_hours'], 
                  data['insider_conviction'], entry_price, data['target_price'], data['stop_loss'], iv_rank, premium_usd)
    return data, ticker, stats, entry_price

def format_telegram_msg(ticker, data, stats, label="SIGNAL"):
    insider_tag = "🚨 <b>INSIDER ALERT</b>" if data['is_insider'] else "📊 <b>STANDARD FLOW</b>"
    golden_tag = "🏆 <b>GOLDEN SWEEP DETECTED</b>\n" if data.get('is_golden_sweep') else ""
    iv_box = f"⚠️ <b>{data['iv_warning']}</b>\n━━━━━━━━━━━━━━━━━\n" if data['iv_warning'] else ""
    return (f"🚀 <b>FLOWGOD {label}: {ticker}</b>\n{insider_tag}\n{golden_tag}━━━━━━━━━━━━━━━━━\n{iv_box}"
            f"🔥 <b>Conviction:</b> {data['insider_conviction']}/10\n📊 <b>Action:</b> <code>{data['direction']}</code>\n"
            f"🎯 <b>Target:</b> <code>${data['target_price']}</code>\n🧐 <b>ANALYSIS:</b> <i>{data['analysis']}</i>")

async def handle_telegram_inbound(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID): return
    status_msg = await update.message.reply_text("🧠 <b>FlowGod is analyzing...</b>", parse_mode='HTML')
    data, ticker, stats, entry_price = await perform_full_analysis(update.message.text)
    if data:
        await update.message.reply_text(format_telegram_msg(ticker, data, stats, "REQUEST"), parse_mode='HTML')
    await status_msg.delete()

async def process_scraped_messages():
    if not os.path.exists('unusual_messages.json'): return
    with open('unusual_messages.json', 'r') as f: scraped = json.load(f)
    processed = []
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f: processed = json.load(f)
    for msg in scraped:
        content = msg['content']
        if content in processed: continue
        data, ticker, stats, entry_price = await perform_full_analysis(content)
        if data and data != "STORED":
            bot = Bot(token=TELEGRAM_TOKEN)
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=format_telegram_msg(ticker, data, stats, "AUTOPILOT"), parse_mode='HTML')
        processed.append(content)
        if len(processed) > 500: processed.pop(0)
    with open(PROCESSED_FILE, 'w') as f: json.dump(processed, f)

async def main():
    if not TELEGRAM_TOKEN: return
    if os.path.exists('unusual_messages.json'):
        await process_scraped_messages()
        if datetime.now().hour >= 21: await send_daily_trends()
        return
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_telegram_inbound))
    asyncio.create_task(app.run_polling())
    if DISCORD_TOKEN:
        client = discord.Client(intents=discord.Intents.default()); await client.start(DISCORD_TOKEN)
    else:
        while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
