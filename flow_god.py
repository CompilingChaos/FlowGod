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
from database import init_db, log_trade, get_performance_stats, log_long_term_flow, get_daily_trends, log_report, get_last_week_reports, clear_daily_flow, get_ticker_daily_stats, get_daily_trades, get_daily_performance_stats

load_dotenv()
init_db()

# Config
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEYS = [k.strip() for k in os.getenv('GEMINI_API_KEYS', '').split(',') if k.strip()]
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
PROCESSED_FILE = 'processed_messages.json'

STOP_WORDS = {"CALL", "PUT", "ALERT", "BUY", "SELL", "LONG", "SHORT", "ASK", "BID", "FLOW", "SIZE", "SWEEP", "BLOCK"}

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
    """Compile, summarize with AI, and send daily smart money trends and performance to Telegram."""
    trends = get_daily_trends()
    daily_trades = get_daily_trades()
    perf_stats = get_daily_performance_stats()
    
    if not trends and not daily_trades and not perf_stats: return
    
    past_reports = get_last_week_reports()
    
    trends_raw = "\n".join([f"{t}: {d}, ${p/1e6:.1f}M ({c} orders)" for t, d, p, c in trends])
    trades_raw = "\n".join([f"{t}: {d}, Price: ${ep}, Conv: {cs}, Prem: ${p/1e3:.1f}k" for t, d, ep, tp, sl, cs, p in daily_trades])
    
    # Format performance statistics
    perf_raw = "No trades closed today."
    perfect_raw = "None"
    if perf_stats:
        perf_raw = (f"Total Closed (Timeframe Ended): {perf_stats['total']}\n"
                   f"Successful Wins: {perf_stats['wins']}\n"
                   f"Today's Accuracy: {perf_stats['win_rate']:.1f}%\n"
                   f"Avg Leveraged ROI: {perf_stats['avg_pnl']:+.1f}%")
        
        if perf_stats['perfect_convictions']:
            perfect_raw = "\n".join([f"{t['ticker']} ({t['direction']}): {t['pnl']:+.1f}% ROI" for t in perf_stats['perfect_convictions']])

    history_context = "\n---\n".join(past_reports) if past_reports else "No historical reports available."
    
    prompt = f"""
    You are the FlowGod institutional analyst. Summarize today's Smart Money Activity, Important Events, and Performance.
    
    LONG-TERM FLOW (>30 DTE):
    {trends_raw}
    
    TODAY'S NEW SIGNALS/TRADES:
    {trades_raw}
    
    TODAY'S PERFORMANCE (Trades whose timeframe ended today):
    {perf_raw}
    
    10/10 CONVICTION PERFORMANCE TODAY:
    {perfect_raw}
    
    PAST WEEK'S SUMMARIES FOR CONTEXT:
    {history_context}
    
    INSTRUCTIONS:
    1. Identify where 'Smart Money' is moving.
    2. Highlight significant events/themes.
    3. Analyze today's accuracy and performance. Be critical if the win rate is low.
    4. Explicitly mention the performance of any 10/10 conviction trades that were closed today.
    5. Format in clean HTML for Telegram.
    6. End with a "Market Sentiment" score (1-10) and a brief "Outlook" for tomorrow.
    """
    summary = "Unable to generate summary."
    keys = list(GEMINI_API_KEYS)
    random.shuffle(keys)
    for key in keys:
        try:
            client = genai.Client(api_key=key)
            response = await asyncio.to_thread(client.models.generate_content, model='gemini-3-flash-preview', contents=prompt)
            summary = response.text
            break
        except Exception as e:
            print(f"⚠️ Daily trend AI summary failed: {e}")
            continue
    log_report(summary)
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"📊 <b>END-OF-DAY SMART MONEY & PERFORMANCE INTELLIGENCE</b>\n\n{summary}", parse_mode='HTML')
    clear_daily_flow()

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

async def get_macro_context():
    try:
        spy = yf.Ticker("SPY")
        hist = await asyncio.to_thread(spy.history, period="2d")
        spy_ret = (hist['Close'].iloc[-1] / hist['Close'].iloc[-2] - 1) * 100
        
        qqq = yf.Ticker("QQQ")
        hist_q = await asyncio.to_thread(qqq.history, period="2d")
        qqq_ret = (hist_q['Close'].iloc[-1] / hist_q['Close'].iloc[-2] - 1) * 100
        
        return f"SPY: {spy_ret:+.2f}%, QQQ: {qqq_ret:+.2f}%"
    except Exception as e: 
        print(f"⚠️ Macro context failed: {e}")
        return "Macro data unavailable."

async def analyze_with_ai_retry(trade_content, news_context, stats, market_data, daily_context):
    keys = list(GEMINI_API_KEYS)
    random.shuffle(keys)
    prompt = f"""
    Analyze this Unusual Options trade report:
    {trade_content}
    QUANTITATIVE & OPTION DATA:
    {market_data}
    CUMULATIVE DAILY CONTEXT FOR THIS TICKER:
    {daily_context}
    NEWS & FILINGS:
    {news_context}
    HISTORICAL PERFORMANCE:
    {stats}
    Return a JSON object with: is_insider, insider_conviction (1-10), is_golden_sweep, iv_warning, insider_logic (HTML), meaningfulness, direction (LONG/SHORT), leverage, timeframe_hours, timeframe_text (human-readable), target_price, stop_loss, analysis (HTML).
    """
    for key in keys:
        try:
            client = genai.Client(api_key=key)
            response = await asyncio.to_thread(client.models.generate_content,
                model='gemini-3-flash-preview',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type='application/json')
            )
            data = json.loads(response.text)
            return data[0] if isinstance(data, list) else data
        except Exception as e:
            print(f"⚠️ AI analysis failed with key {key[:5]}...: {e}")
            await asyncio.sleep(2)
    return None

def _sync_fetch_news(ticker, query_type="general"):
    """Sync news search for use in to_thread."""
    yesterday = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    query = f'site:sec.gov "{ticker}" ("Form 4" OR "13D" OR "13G") after:{yesterday}' if query_type == "sec" else f"{ticker} stock news insider catalyst after:{yesterday}"
    return list(search(query, num_results=3, lang="en"))

async def fetch_news(ticker, query_type="general"):
    """Fetch news with a strict internal timeout to prevent hanging."""
    try:
        print(f"🔍 Searching news for {ticker} ({query_type})...")
        results = await asyncio.wait_for(asyncio.to_thread(_sync_fetch_news, ticker, query_type), timeout=30)
        return "\n".join(results)
    except Exception as e:
        print(f"⚠️ News search failed for {ticker} ({query_type}): {e}")
        return "No recent data found."

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
    entry_price = 0
    market_data = "Scanning for data..."
    
    try:
        tk = yf.Ticker(ticker)
        print(f"📊 Fetching history for {ticker}...")
        hist_full = await asyncio.wait_for(asyncio.to_thread(tk.history, period="1y"), timeout=20)
        entry_price = round(hist_full['Close'].iloc[-1], 2)
        
        print(f"📊 Fetching info for {ticker}...")
        info = await asyncio.wait_for(asyncio.to_thread(lambda: tk.info), timeout=20)
        mkt_cap = (info.get('marketCap') or info.get('totalAssets', 0)) if info else 0
        
        sma50 = round(hist_full['Close'].rolling(50).mean().iloc[-1], 2)
        rsi = round(calculate_rsi(hist_full['Close']).iloc[-1], 2)
        macro = await get_macro_context()
        
        # 2. Market Cap Relative Filtering
        threshold = get_mkt_cap_threshold(mkt_cap)
        if premium_usd > 0 and premium_usd < threshold:
            print(f"⏭️ {ticker} filtered by market cap threshold (${threshold/1e3:.0f}k)")
            return "FILTERED_BY_CAP", ticker, None, 0, stable_id

        golden_sweep_context = f"UNUSUALLY HIGH VOL/OI ({vol_oi}x)" if vol_oi > 2.0 else "Standard liquidity"
        market_data = (f"Ticker: {ticker} @ ${entry_price} | Size: {mkt_cap/1e9:.1f}B | IV Rank: {iv_rank}%\n"
                      f"Option: {strike_val} {option_type} Exp {expiry_val} | Side: {side} (Aggression: {ask_pct}% Ask)\n"
                      f"Context: {multi_pct}% Multi-leg | Vol/OI: {vol_oi} ({golden_sweep_context})\n"
                      f"Metrics: RSI={rsi}, 50SMA=${sma50} | Macro: {macro}")
    except Exception as e:
        print(f"⚠️ Market data fetch failed for {ticker}: {e}")
        if premium_usd > 0 and premium_usd < 100000: return None, ticker, None, 0, stable_id
        market_data = "Data fetch partially failed."

    # Parallelize news fetching
    news_task = fetch_news(ticker)
    sec_task = fetch_news(ticker, query_type="sec")
    news, sec = await asyncio.gather(news_task, sec_task)
    
    stats = get_performance_stats()
    d_stats = get_ticker_daily_stats(ticker)
    daily_context = f"This day there have been {d_stats['CALL']['count']} call alerts with a total premium of ${d_stats['CALL']['prem']/1e3:.0f}k and {d_stats['PUT']['count']} puts with a premium of ${d_stats['PUT']['prem']/1e3:.0f}k."
    
    # --- RESTORED: Long-term flow logging for Daily Trends ---
    if is_long_term(expiry_val):
        log_long_term_flow(ticker, option_type, strike_val, expiry_val, premium_usd, vol_oi, 0, side)
        return "STORED", ticker, None, 0, stable_id

    print(f"🧠 Running AI analysis for {ticker}...")
    data = await analyze_with_ai_retry(trade_info, news + "\n" + sec, stats, market_data, daily_context)
    
    if not data:
        return None, ticker, stats, entry_price, stable_id

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
    timeframe_txt = data.get('timeframe_text', 'N/A')
    target = safe_num(data.get('target_price'), 0)
    stop = safe_num(data.get('stop_loss'), 0)
    conviction = int(safe_num(data.get('insider_conviction'), 7))

    # 3. Strategic Calibration
    if side == "Bid" and option_type == "Puts":
        data['direction'] = "LONG"
        data['analysis'] = "<b>[BID SIDE PUTS]</b> Bullish premium selling. " + (data.get('analysis') or "")
    elif side == "Bid" and option_type == "Calls":
        data['direction'] = "SHORT"
        data['analysis'] = "<b>[BID SIDE CALLS]</b> Bearish premium selling. " + (data.get('analysis') or "")
    
    if ask_pct >= 70 and multi_pct == 0:
        conviction = min(10, conviction + 2)
        data['analysis'] = "🔥 <b>HIGH URGENCY:</b> Naked ask-side aggression. " + (data.get('analysis') or "")

    if entry_price > 0:
        log_trade(ticker, data.get('direction', 'LONG'), leverage, timeframe, conviction, entry_price, target, stop, iv_rank, premium_usd, option_entry)
    
    # Update data dict for format_telegram_msg consistency
    data['insider_conviction'] = conviction
    data['leverage'] = leverage
    data['timeframe_hours'] = timeframe
    data['timeframe_text'] = timeframe_txt
    data['target_price'] = target
    data['stop_loss'] = stop
    data['premium'] = premium_usd
    data['entry_price'] = entry_price
    
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
    is_insider = data.get('is_insider')
    analysis_text = data.get('analysis', "No analysis available.")
    
    header_tag = "🚨 <b>INSIDER ALERT</b>" if is_insider else "📊 <b>STANDARD FLOW</b>"
    
    # 2. Add 'Longterm Idea' branding for Floor Support trades
    if "[BID SIDE PUTS]" in analysis_text or "[BID SIDE CALLS]" in analysis_text:
        header_tag = "🛡️ <b>LONG-TERM IDEA / FLOOR SUPPORT</b>"
    
    golden_tag = "🏆 <b>GOLDEN SWEEP DETECTED</b>\n" if data.get('is_golden_sweep') else ""
    iv_msg = "HIGH IV RISK" if data.get('iv_warning') is True else data.get('iv_warning')
    iv_box = f"⚠️ <b>{iv_msg}</b>\n━━━━━━━━━━━━━━━━━\n" if data.get('iv_warning') else ""
    
    clean_analysis = clean_html(analysis_text)
    premium_str = f"${data.get('premium', 0):,.0f}" if isinstance(data.get('premium'), (int, float)) else str(data.get('premium'))

    return (f"<b>FLOWGOD: {ticker}</b>\n{header_tag}\n{golden_tag}━━━━━━━━━━━━━━━━━\n{iv_box}"
            f"🔥 <b>Conviction:</b> {data.get('insider_conviction')}/10\n"
            f"💰 <b>Premium:</b> <code>{premium_str}</code>\n"
            f"📈 <b>Buy in:</b> <code>${data.get('entry_price', 0)}</code>\n"
            f"📊 <b>Action:</b> <code>{data.get('direction')}</code>\n"
            f"🎯 <b>Target:</b> <code>${data.get('target_price')}</code>\n"
            f"⏳ <b>Timeframe:</b> <code>{data.get('timeframe_text', 'N/A')}</code>\n"
            f"🧐 <b>ANALYSIS:</b> <i>{clean_analysis}</i>")

async def process_scraped_messages():
    if not os.path.exists('unusual_messages.json'): return
    with open('unusual_messages.json', 'r') as f: scraped = json.load(f)
    
    # 4. Parent-Child Deduplication
    unique_signals = {}
    for msg in scraped:
        content = msg['content']
        prem_match = re.search(r'Prem(?:ium)?:\s*\$([\d\.,]+[KMB]?)', content, re.I)
        premium = parse_premium(prem_match.group(1) if prem_match else "0")
        is_hot = "🔥" in content or "Hot Contract" in content
        
        ts_match = re.search(r'([A-Z]{1,5})\s+([\d\.]+)\s+([CP])\s+([\d\/]{8,10})', content, re.DOTALL)
        side_match = re.search(r'(Ask|Bid|Mid)\s+Side', content, re.I)
        if not ts_match: continue
        
        ticker = ts_match.group(1).upper()
        strike = ts_match.group(2); expiry = ts_match.group(4); side = side_match.group(1).capitalize() if side_match else "Unknown"
        time_id = normalize_reported_time(content)
        
        sid = get_stable_id(ticker, strike, expiry, side, time_id)
        if sid not in unique_signals or (is_hot and not unique_signals[sid]['is_hot']) or (premium > unique_signals[sid]['premium'] * 1.1):
            unique_signals[sid] = {"content": content, "premium": premium, "is_hot": is_hot}

    processed = []
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f: processed = json.load(f)
    
    print(f"📦 Processing {len(unique_signals)} unique signals...")
    
    semaphore = asyncio.Semaphore(3) # Process 3 at a time to avoid rate limits

    async def analyze_and_send(sid, signal):
        async with semaphore:
            if sid in processed: return
            print(f"🔮 Analyzing signal for {sid[:8]}...")
            try:
                # Use a global timeout of 120s per signal analysis
                res = await asyncio.wait_for(perform_full_analysis(signal['content']), timeout=120)
                data, ticker, stats, entry_price, stable_id = res
                
                if data and data not in ["STORED", "FILTERED_BY_CAP"] and data.get('insider_conviction', 0) >= 6:        
                    bot = Bot(token=TELEGRAM_TOKEN)
                    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=format_telegram_msg(ticker, data, stats), parse_mode='HTML')
                    print(f"✅ Signal sent for {ticker}")
                processed.append(sid)
            except asyncio.TimeoutError:
                print(f"⌛ Timeout analyzing signal for {sid[:8]}")
            except Exception as e:
                print(f"❌ Error analyzing signal for {sid[:8]}: {e}")

    tasks = [analyze_and_send(sid, signal) for sid, signal in unique_signals.items()]
    await asyncio.gather(*tasks)

    if len(processed) > 500: processed = processed[-500:]
    with open(PROCESSED_FILE, 'w') as f: json.dump(processed, f)

async def main():
    if not TELEGRAM_TOKEN: return
    
    # Process standard signals
    if os.path.exists('unusual_messages.json'):
        await process_scraped_messages()
    
    # At 4 PM EST (21:00 UTC), send daily trends
    if datetime.now().hour >= 21:
        print("🕒 EOD window detected. Compiling daily trends...")
        await send_daily_trends()

if __name__ == "__main__":
    asyncio.run(main())
