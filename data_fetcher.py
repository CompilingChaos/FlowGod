import yfinance as yf
import pandas as pd
import requests
import time
import logging
import re
import numpy as np
from datetime import datetime, timedelta
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from config import CLOUDFLARE_PROXY_URL
from error_reporter import notify_error_sync

# SEC EDGAR requires a compliant User-Agent
SEC_HEADERS = {"User-Agent": "FlowGod-Whale-Tracker (admin@flowgod.ai) - Research Bot"}
CIK_MAPPING_URL = "https://www.sec.gov/files/company_tickers.json"
_cik_cache = {}

def _load_cik_mapping():
    global _cik_cache
    if _cik_cache: return
    try:
        response = requests.get(CIK_MAPPING_URL, headers=SEC_HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for key in data:
                ticker = data[key]['ticker'].upper()
                cik = str(data[key]['cik_str']).zfill(10)
                _cik_cache[ticker] = cik
            logging.info(f"📁 Loaded {len(_cik_cache)} Ticker-to-CIK mappings from SEC.")
    except Exception as e:
        logging.error(f"Failed to load SEC CIK mapping: {e}")

def get_sec_filings(ticker):
    """
    Tier-4: Ghost Filing Correlation.
    Fetches the last 5 submissions for a ticker to identify insider/institutional activity.
    """
    _load_cik_mapping()
    cik = _cik_cache.get(ticker.upper())
    if not cik: return []
    
    try:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        response = requests.get(url, headers=SEC_HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            recent = data.get('filings', {}).get('recent', {})
            forms = recent.get('form', [])
            dates = recent.get('filingDate', [])
            filings = []
            for i in range(min(5, len(forms))):
                form = forms[i]
                date = dates[i]
                if form in ['4', '13D', '13G']:
                    filings.append({'form': form, 'date': date})
            return filings
        return []
    except Exception as e:
        logging.warning(f"SEC fetch failed for {ticker}: {e}")
        return []

# --- Cloudflare Bridge Monkey Patch ---
if CLOUDFLARE_PROXY_URL:
    try:
        original_request = requests.Session.request
        proxy_url = CLOUDFLARE_PROXY_URL.rstrip('/')
        def proxied_request(self, method, url, *args, **kwargs):
            if "finance.yahoo.com" in url:
                new_url = re.sub(r'https://query\d\.finance\.yahoo\.com', proxy_url, url)
                return original_request(self, method, new_url, *args, **kwargs)
            return original_request(self, method, url, *args, **kwargs)
        requests.Session.request = proxied_request
        logging.info(f"✅ Cloudflare Bridge Patched: {proxy_url}")
    except Exception as e:
        notify_error_sync("DATA_FETCHER_PATCH", e, "Failed to apply Cloudflare Bridge monkey patch.")

def get_market_regime():
    """
    Pillar 1: Dynamic Market Regime Sensor.
    Detects if the market is in 'Risk-On', 'Risk-Off', or 'High-Volatility Squeeze' state.
    """
    try:
        vix = yf.Ticker("^VIX").fast_info.get('lastPrice', 20)
        spy_change = yf.Ticker("SPY").fast_info.get('day_change_percent', 0)
        
        if vix > 25: return "HIGH_VOLATILITY"
        if spy_change < -1.5 and vix > 20: return "RISK_OFF"
        if spy_change > 0.5 and vix < 18: return "RISK_ON"
        return "NEUTRAL"
    except:
        return "NEUTRAL"

def get_sector_divergence(ticker, sector):
    """
    Pillar 3: Cross-Asset Hedge Detection.
    Checks if a ticker is moving against its sector ETF (Divergence = High Conviction).
    """
    sector_map = {'Technology': 'XLK', 'Healthcare': 'XLV', 'Financial': 'XLF', 'Energy': 'XLE', 'Consumer Cyclical': 'XLY', 'Communication Services': 'XLC', 'Semiconductors': 'SMH'}
    etf_symbol = sector_map.get(sector)
    if not etf_symbol: return "Correlated"
    
    try:
        t_info = yf.Ticker(ticker).fast_info
        e_info = yf.Ticker(etf_symbol).fast_info
        
        ticker_change = t_info.get('day_change_percent', 0)
        etf_change = e_info.get('day_change_percent', 0)
        
        if ticker_change > 1.0 and etf_change < -0.5: return "Relative Strength"
        if ticker_change < -2.0 and etf_change > -0.2: return "Isolated Weakness"
        return "Correlated"
    except:
        return "Correlated"

def get_advanced_macro():
    """Fetches global macro context (SPY, VIX, DXY, TNX, QQQ) for institutional analysis."""
    try:
        tickers = ["SPY", "^VIX", "DX-Y.NYB", "^TNX", "QQQ"]
        data = {}
        for t in tickers:
            info = yf.Ticker(t).fast_info
            data[t] = info.get('day_change_percent', 0)
        
        spy_pc, vix_pc = data.get("SPY", 0), data.get("^VIX", 0)
        dxy_pc, tnx_pc = data.get("DX-Y.NYB", 0), data.get("^TNX", 0)
        qqq_pc = data.get("QQQ", 0)
        
        sentiment = "Neutral"
        if spy_pc < -1.0 and vix_pc > 5.0: sentiment = "Fearful / Risk-Off"
        if spy_pc > 0.5 and vix_pc < -3.0: sentiment = "Bullish / Risk-On"
        if dxy_pc > 0.5: sentiment += " | Liquidity Squeeze (DXY Up)"
        if tnx_pc > 1.0: sentiment += " | Tech Pressure (TNX Up)"
        return {'spy': round(spy_pc, 2), 'vix': round(vix_pc, 2), 'dxy': round(dxy_pc, 2), 'tnx': round(tnx_pc, 2), 'qqq': round(qqq_pc, 2), 'sentiment': sentiment}
    except Exception as e:
        notify_error_sync("DATA_FETCHER_MACRO", e, "Macro data fetch failure.")
        return {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'qqq': 0, 'sentiment': "Unknown"}

def get_sector_etf_performance():
    etfs = {'Technology': 'XLK', 'Healthcare': 'XLV', 'Financial': 'XLF', 'Energy': 'XLE', 'Consumer Cyclical': 'XLY', 'Communication Services': 'XLC', 'Semiconductors': 'SMH'}
    performance = {}
    for sector, symbol in etfs.items():
        try:
            ticker = yf.Ticker(symbol)
            performance[sector] = ticker.fast_info.get('day_change_percent', 0)
        except Exception as e:
            logging.warning(f"Sector fetch failed for {sector}: {e}")
            performance[sector] = 0
    return performance

def get_intraday_aggression(ticker):
    """Analyzes 1m price action for TRV and Dark Pool Proxies."""
    try:
        df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if df.empty or len(df) < 10: return None
        
        # VWAP
        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['Cumulative_Vol'] = df['Volume'].cumsum()
        df['Cumulative_Vol_Price'] = (df['Typical_Price'] * df['Volume']).cumsum()
        df['VWAP'] = df['Cumulative_Vol_Price'] / df['Cumulative_Vol']
        
        # Dark Pool Proxy: Volume Density (Vol / Price Range)
        df['price_range'] = (df['High'] - df['Low']).replace(0, 0.01)
        df['vol_density'] = df['Volume'] / df['price_range']
        rolling_mean = df['vol_density'].rolling(window=30).mean()
        rolling_std = df['vol_density'].rolling(window=30).std()
        df['dark_z'] = (df['vol_density'] - rolling_mean) / (rolling_std + 0.001)
        
        candle = df.iloc[-1].to_dict()
        candle['vwap'] = df['VWAP'].iloc[-1]
        candle['dark_z_max'] = float(df['dark_z'].iloc[-5:].max())
        candle['prev_close'] = float(df['Close'].iloc[-2])
        return candle
    except Exception as e:
        logging.error(f"Intraday analysis failed for {ticker}: {e}")
        return None

def get_stock_info(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        return {'price': info.get('lastPrice', 0), 'volume': info.get('last_volume', 0)}
    except Exception as e:
        logging.error(f"Stock info fetch failed for {ticker}: {e}")
        return {'price': 0, 'volume': 0}

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(2))
def get_option_chain_data(ticker, price, stock_vol, full_chain=False):
    """Fetches option chains. If full_chain=True, fetches next 15 expirations for Walls."""
    stock = yf.Ticker(ticker)
    all_data = []
    try:
        options = list(stock.options)
        if not options: return pd.DataFrame()
        
        limit = 15 if full_chain else 5
        for exp in options[:limit]:
            chain = stock.option_chain(exp)
            for side_name, side in [("calls", chain.calls), ("puts", chain.puts)]:
                if side.empty: continue
                side = side.copy()
                side['ticker'], side['exp'], side['side'] = ticker, exp, side_name
                side['dte'] = (pd.to_datetime(exp) - pd.Timestamp.now()).days
                side['notional'] = side['volume'] * side['lastPrice'].fillna(0) * 100
                side['vol_oi_ratio'] = side['volume'] / (side['openInterest'].replace(0, 1) + 1)
                side['underlying_price'], side['underlying_vol'] = price, stock_vol
                side['moneyness'] = abs(side['strike'] - price) / price * 100 if price > 0 else 0
                all_data.append(side)
            time.sleep(0.6)
    except Exception as e:
        logging.error(f"Option fetch failed for {ticker}: {e}")
        notify_error_sync("DATA_FETCHER_OPTIONS", e, f"Failed to fetch option chain for {ticker}.")
    return pd.concat(all_data) if all_data else pd.DataFrame()

def get_contract_oi(contract_symbol):
    try:
        ticker_match = re.match(r'^([A-Z]+)', contract_symbol)
        if not ticker_match: return 0
        ticker = ticker_match.group(1)
        stock = yf.Ticker(ticker)
        for exp in stock.options[:10]:
            chain = stock.option_chain(exp)
            for side in [chain.calls, chain.puts]:
                match = side[side['contractSymbol'] == contract_symbol]
                if not match.empty: return int(match.iloc[0]['openInterest'])
        return 0
    except Exception as e:
        logging.warning(f"OI fetch failed for {contract_symbol}: {e}")
        return 0

def get_social_velocity(ticker):
    """
    Tier-3 Social Sentiment Scraper.
    Derives real message volume from StockTwits public feed.
    """
    try:
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            messages = data.get('messages', [])
            return float(len(messages))
        return 0.0
    except Exception as e:
        logging.warning(f"Social Velocity failed for {ticker}: {e}")
        return 0.0
