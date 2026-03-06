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

def get_stable_id(ticker, strike, expiry, side, reported_time):
    """Create a unique hash for a trade. Premium is excluded to group Interval/Hot alerts."""
    unique_str = f"{ticker}_{strike}_{expiry}_{side}_{reported_time}"
    return hashlib.sha256(unique_str.encode()).hexdigest()

def normalize_reported_time(text):
    """Convert 'gestern um 21:40' or 'heute um 14:00' to a stable ISO date string."""
    now = datetime.now()
    time_match = re.search(r'(\d{1,2}):(\d{2})', text)
    if not time_match: return now.strftime('%Y-%m-%d')
    
    hour, minute = map(int, time_match.groups())
    target_date = now
    if "gestern" in text.lower():
        target_date = now - timedelta(days=1)
    
    return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat()

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
            data = json.loads(response.text)
            return data[0] if isinstance(data, list) else data
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

def get_stable_id(ticker, strike, expiry, side, reported_time):
    """Create a unique hash for a trade. Premium is excluded to group Interval/Hot alerts."""
    unique_str = f"{ticker}_{strike}_{expiry}_{side}_{reported_time}"
    return hashlib.sha256(unique_str.encode()).hexdigest()

def get_mkt_cap_threshold(mkt_cap):
    """Sliding scale for premium floor based on ticker size."""
    # Convert to Billions for easy comparison
    cap_b = mkt_cap / 1e9
    if cap_b < 10: return 100000      # Small Cap: $100k
    if cap_b < 50: return 300000      # Mid Cap: $300k
    if cap_b < 200: return 500000     # Large Cap: $500k
    return 2000000                    # Mega Cap (NVDA, MSFT, etc): $2M

async def perform_full_analysis(trade_info, msg_time=None):
    """Core analysis logic reusable for Discord or Telegram."""
    clean_info = str(trade_info).replace("🔥", "").replace("🚨", "").strip()
    
    # 1. Flexible Multi-line Extraction
    ts_match = re.search(r'([A-Z]{1,5})\s+([\d\.]+)\s+([CP])\s+([\d\/]{8,10})', clean_info, re.DOTALL)
    side_match = re.search(r'(Ask|Bid|Mid)\s+Side', clean_info, re.I)
    ba_match = re.search(r'Bid/Ask %:\s*(\d+)/(\d+)', clean_info)
    multi_match = re.search(r'Multi-leg Volume:\s*(\d+)%', clean_info)
    prem_match = re.search(r'Prem(?:ium)?:\s*\$([\d\.,]+[KMB]?)', clean_info, re.I)
    fill_match = re.search(r'Average Fill:\s*\$([\d\.]+)', clean_info, re.I)
    vol_oi_match = re.search(r'Vol/OI:\s*([\d\.]+)', clean_info, re.I)
    time_str = normalize_reported_time(clean_info)

    side = side_match.group(1).capitalize() if side_match else "Unknown"
    ask_pct = int(ba_match.group(2)) if ba_match else 50
    multi_pct = int(multi_match.group(1)) if multi_match else 0
    premium_usd = parse_premium(prem_match.group(1) if prem_match else "0")
    option_entry = float(fill_match.group(1)) if fill_match else 0.0
    vol_oi = float(vol_oi_match.group(1)) if vol_oi_match else 0.0

    if ts_match:
        ticker = ts_match.group(1).upper()
        strike_val = ts_match.group(2); option_type = "Calls" if ts_match.group(3).upper() == "C" else "Puts"; expiry_val = ts_match.group(4)
    else:
        ticker_match = re.search(r'^([A-Z]{1,5})\b', clean_info)
        ticker = ticker_match.group(1).upper() if ticker_match else "SPY"
        strike_match = re.search(r'\b([\d\.]+)\s+([CP])\b', clean_info)
        strike_val = strike_match.group(1) if strike_match else "N/A"
        option_type = "Calls" if (strike_match and strike_match.group(2) == "C") else "Options"
        expiry_match = re.search(r'(\d{2}/\d{2}/\d{4})', clean_info)
        expiry_val = expiry_match.group(1) if expiry_match else "N/A"

    stable_id = get_stable_id(ticker, strike_val, expiry_val, side, time_str)

    iv_rank = calculate_iv_rank(ticker)
    try:
        tk = yf.Ticker(ticker); hist_full = tk.history(period="1y"); entry_price = round(hist_full['Close'].iloc[-1], 2); mkt_cap = (tk.info.get('marketCap') or tk.info.get('totalAssets', 0)) if tk.info else 0
        sma50 = round(hist_full['Close'].rolling(50).mean().iloc[-1], 2); rsi = round(calculate_rsi(hist_full['Close']).iloc[-1], 2); macro = await get_macro_context()
        
        # 2. Market Cap Relative Filtering
        threshold = get_mkt_cap_threshold(mkt_cap)
        if premium_usd < threshold:
            return "FILTERED_BY_CAP", ticker, None, 0, stable_id

        golden_sweep_context = f"UNUSUALLY HIGH VOL/OI ({vol_oi}x)" if vol_oi > 2.0 else "Standard liquidity"
        market_data = (f"Ticker: {ticker} @ ${entry_price} | Size: {mkt_cap/1e9:.1f}B | IV Rank: {iv_rank}%\n"
                      f"Option: {strike_val} {option_type} Exp {expiry_val} | Side: {side} (Aggression: {ask_pct}% Ask)\n"
                      f"Context: {multi_pct}% Multi-leg | Vol/OI: {vol_oi} ({golden_sweep_context})\n"
                      f"Metrics: RSI={rsi}, 50SMA=${sma50} | Macro: {macro}")
    except:
        if premium_usd < 100000: return None, ticker, None, 0, stable_id
        entry_price, market_data = 0, "Data fetch failed."

    if is_long_term(expiry_val):
        log_long_term_flow(ticker, option_type, strike_val, expiry_val, premium_usd, vol_oi, 0, side)
        return "STORED", ticker, None, 0, stable_id

    news = fetch_news(ticker); sec = fetch_news(ticker, query_type="sec"); stats = get_performance_stats()
    d_stats = get_ticker_daily_stats(ticker)
    daily_context = f"This day there have been {d_stats['CALL']['count']} call alerts with a total premium of ${d_stats['CALL']['prem']/1e3:.0f}k and {d_stats['PUT']['count']} puts with a premium of ${d_stats['PUT']['prem']/1e3:.0f}k."
    data = await analyze_with_ai_retry(trade_info, news + "\n" + sec, stats, market_data, daily_context)
    
    if not data: return None, ticker, stats, entry_price, stable_id

    # --- ROBUST NUMERIC PARSING ---
    # Ensure AI-returned strings are converted to numbers before DB logging
    def safe_num(val, default=0):
        try:
            if isinstance(val, (int, float)): return val
            # Remove non-numeric artifacts like 'x' or ' (OTM)'
            clean_val = re.sub(r'[^\d\.]', '', str(val))
            return float(clean_val) if clean_val else default
        except: return default

    leverage = safe_num(data.get('leverage'), 5)
    timeframe = safe_num(data.get('timeframe_hours'), 24)
    target = safe_num(data.get('target_price'), 0)
    stop = safe_num(data.get('stop_loss'), 0)
    conviction = int(safe_num(data.get('insider_conviction'), 7))

    # 3. Strategic Calibration
    if side == "Bid" and option_type == "Puts":
        data['direction'] = "LONG"
        data['analysis'] = "<b>[BID SIDE PUTS]</b> Bullish premium selling. " + data['analysis']
    elif side == "Bid" and option_type == "Calls":
        data['direction'] = "SHORT"
        data['analysis'] = "<b>[BID SIDE CALLS]</b> Bearish premium selling. " + data['analysis']
    
    if ask_pct >= 70 and multi_pct == 0:
        conviction = min(10, conviction + 2)
        data['analysis'] = "🔥 <b>HIGH URGENCY:</b> Naked ask-side aggression. " + data['analysis']

    if entry_price > 0:
        log_trade(ticker, data['direction'], leverage, timeframe, conviction, entry_price, target, stop, iv_rank, premium_usd, option_entry)
    
    # Update data dict for format_telegram_msg consistency
    data['insider_conviction'] = conviction
    data['leverage'] = leverage
    data['timeframe_hours'] = timeframe
    data['target_price'] = target
    data['stop_loss'] = stop
    
    return data, ticker, stats, entry_price, stable_id

def clean_html(text):
    """Sanitize HTML for Telegram: replace <br> with newlines and remove unsupported tags."""
    if not text: return ""
    # Replace <br>, <br/>, <br /> with \n
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    # Ensure only Telegram-supported tags remain (basic b, i, code, u, s)
    return text

def format_telegram_msg(ticker, data, stats, label="SIGNAL"):
    # 1. Determine the 'Vibe' of the trade
    is_insider = data['is_insider']
    analysis_text = data['analysis']
    
    header_tag = "🚨 <b>INSIDER ALERT</b>" if is_insider else "📊 <b>STANDARD FLOW</b>"
    
    # 2. Add 'Longterm Idea' branding for Floor Support trades
    if "[BID SIDE PUTS]" in analysis_text or "[BID SIDE CALLS]" in analysis_text:
        header_tag = "🛡️ <b>LONG-TERM IDEA / FLOOR SUPPORT</b>"
    
    golden_tag = "🏆 <b>GOLDEN SWEEP DETECTED</b>\n" if data.get('is_golden_sweep') else ""
    iv_msg = "HIGH IV RISK" if data['iv_warning'] is True else data['iv_warning']
    iv_box = f"⚠️ <b>{iv_msg}</b>\n━━━━━━━━━━━━━━━━━\n" if data['iv_warning'] else ""
    
    clean_analysis = clean_html(analysis_text)
    
    return (f"<b>FLOWGOD: {ticker}</b>\n{header_tag}\n{golden_tag}━━━━━━━━━━━━━━━━━\n{iv_box}"
            f"🔥 <b>Conviction:</b> {data['insider_conviction']}/10\n📊 <b>Action:</b> <code>{data['direction']}</code>\n"
            f"🎯 <b>Target:</b> <code>${data['target_price']}</code>\n🧐 <b>ANALYSIS:</b> <i>{clean_analysis}</i>")

async def process_scraped_messages():
    if not os.path.exists('unusual_messages.json'): return
    with open('unusual_messages.json', 'r') as f: scraped = json.load(f)
    
    # 4. Parent-Child Deduplication
    # We group by stable_id (Ticker+Strike+Expiry+Side+Time)
    unique_signals = {}
    for msg in scraped:
        content = msg['content']
        # Preliminary pass to extract ID and Premium
        prem_match = re.search(r'Prem(?:ium)?:\s*\$([\d\.,]+[KMB]?)', content, re.I)
        premium = parse_premium(prem_match.group(1) if prem_match else "0")
        
        # Determine if it's a "Hot" version (higher priority)
        is_hot = "🔥" in content or "Hot Contract" in content
        
        # Temporary parsing for grouping
        ts_match = re.search(r'([A-Z]{1,5})\s+([\d\.]+)\s+([CP])\s+([\d\/]{8,10})', content, re.DOTALL)
        side_match = re.search(r'(Ask|Bid|Mid)\s+Side', content, re.I)
        if not ts_match: continue
        
        ticker = ts_match.group(1).upper()
        strike = ts_match.group(2)
        expiry = ts_match.group(4)
        side = side_match.group(1).capitalize() if side_match else "Unknown"
        time_id = normalize_reported_time(content)
        
        sid = get_stable_id(ticker, strike, expiry, side, time_id)
        
        # Store the best version (Hot Contract or highest premium)
        if sid not in unique_signals:
            unique_signals[sid] = {"content": content, "premium": premium, "is_hot": is_hot}
        else:
            # Overwrite if current is Hot and existing isn't, OR if premium is significantly higher
            if (is_hot and not unique_signals[sid]['is_hot']) or (premium > unique_signals[sid]['premium'] * 1.1):
                unique_signals[sid] = {"content": content, "premium": premium, "is_hot": is_hot}

    processed = []
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f: processed = json.load(f)
    
    for sid, signal in unique_signals.items():
        if sid in processed:
            print(f"⏭️ Skipping duplicate: {sid[:10]}")
            continue
            
        data, ticker, stats, entry_price, stable_id = await perform_full_analysis(signal['content'])
        
        if data and data not in ["STORED", "FILTERED_BY_CAP"] and data['insider_conviction'] >= 6:
            bot = Bot(token=TELEGRAM_TOKEN)
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=format_telegram_msg(ticker, data, stats), parse_mode='HTML')
        
        processed.append(sid)
        if len(processed) > 500: processed.pop(0)
        
    with open(PROCESSED_FILE, 'w') as f: json.dump(processed, f)

async def main():
    if not TELEGRAM_TOKEN: return
    # FlowGod now runs exclusively in Autopilot mode via GitHub Actions
    if os.path.exists('unusual_messages.json'):
        await process_scraped_messages()
        if datetime.now().hour >= 21: await send_daily_trends()
        return
    else:
        print("💡 No message file found. FlowGod is optimized for remote Autopilot execution.")

if __name__ == "__main__":
    asyncio.run(main())
