import yfinance as yf
import pandas as pd
import requests
import time
import logging
import re
import numpy as np
from datetime import datetime
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from config import CLOUDFLARE_PROXY_URL

# --- Cloudflare Bridge Monkey Patch ---
if CLOUDFLARE_PROXY_URL:
    original_request = requests.Session.request
    proxy_url = CLOUDFLARE_PROXY_URL.rstrip('/')
    def proxied_request(self, method, url, *args, **kwargs):
        if "finance.yahoo.com" in url:
            new_url = re.sub(r'https://query\d\.finance\.yahoo\.com', proxy_url, url)
            return original_request(self, method, new_url, *args, **kwargs)
        return original_request(self, method, url, *args, **kwargs)
    requests.Session.request = proxied_request
    logging.info(f"✅ Cloudflare Bridge Patched: {proxy_url}")

def get_advanced_macro():
    """Fetches global macro context (SPY, VIX, DXY, TNX, QQQ) for institutional analysis."""
    try:
        spy = yf.Ticker("SPY")
        vix = yf.Ticker("^VIX")
        dxy = yf.Ticker("DX-Y.NYB")
        tnx = yf.Ticker("^TNX")
        qqq = yf.Ticker("QQQ")
        spy_pc = spy.fast_info.get('day_change_percent', 0)
        vix_pc = vix.fast_info.get('day_change_percent', 0)
        dxy_pc = dxy.fast_info.get('day_change_percent', 0)
        tnx_pc = tnx.fast_info.get('day_change_percent', 0)
        qqq_pc = qqq.fast_info.get('day_change_percent', 0)
        sentiment = "Neutral"
        if spy_pc < -1.0 and vix_pc > 5.0: sentiment = "Fearful / Risk-Off"
        if spy_pc > 0.5 and vix_pc < -3.0: sentiment = "Bullish / Risk-On"
        if dxy_pc > 0.5: sentiment += " | Liquidity Squeeze (DXY Up)"
        if tnx_pc > 1.0: sentiment += " | Tech Pressure (TNX Up)"
        return {'spy': round(spy_pc, 2), 'vix': round(vix_pc, 2), 'dxy': round(dxy_pc, 2), 'tnx': round(tnx_pc, 2), 'qqq': round(qqq_pc, 2), 'sentiment': sentiment}
    except Exception as e:
        return {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'qqq': 0, 'sentiment': "Unknown"}

def get_sector_etf_performance():
    etfs = {'Technology': 'XLK', 'Healthcare': 'XLV', 'Financial': 'XLF', 'Energy': 'XLE', 'Consumer Cyclical': 'XLY', 'Communication Services': 'XLC', 'Semiconductors': 'SMH'}
    performance = {}
    for sector, symbol in etfs.items():
        try:
            ticker = yf.Ticker(symbol)
            performance[sector] = ticker.fast_info.get('day_change_percent', 0)
        except: performance[sector] = 0
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
        df['dark_z'] = (df['vol_density'] - rolling_mean) / rolling_std
        
        # Return full DF for HVN analysis in scanner.py
        return df
    except: return None

def get_stock_info(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        return {'price': info.get('lastPrice', 0), 'volume': info.get('last_volume', 0)}
    except: return {'price': 0, 'volume': 0}

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
                side['bid'], side['ask'] = side['bid'], side['ask']
                all_data.append(side)
            time.sleep(0.6)
    except Exception as e: logging.error(f"Option fetch failed for {ticker}: {e}")
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
    except: return 0
