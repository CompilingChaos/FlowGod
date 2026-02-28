import yfinance as yf
import pandas as pd
import requests
import time
import logging
import re
from datetime import datetime
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from config import CLOUDFLARE_PROXY_URL

# --- Cloudflare Bridge Monkey Patch ---
# This forces yfinance (and all other requests) to route through your Worker
if CLOUDFLARE_PROXY_URL:
    original_request = requests.Session.request
    proxy_url = CLOUDFLARE_PROXY_URL.rstrip('/')

    def proxied_request(self, method, url, *args, **kwargs):
        if "finance.yahoo.com" in url:
            new_url = re.sub(r'https://query\d\.finance\.yahoo\.com', proxy_url, url)
            logging.debug(f"Bridging: {url} -> {new_url}")
            return original_request(self, method, new_url, *args, **kwargs)
        return original_request(self, method, url, *args, **kwargs)

    requests.Session.request = proxied_request
    logging.info(f"✅ Cloudflare Bridge Patched: {proxy_url}")
else:
    logging.error("❌ Cloudflare Bridge DISABLED: CLOUDFLARE_PROXY_URL missing!")
# ---------------------------------------

def get_stock_info(ticker):
    """Fetches just the stock price and volume (Fast/Light)."""
    try:
        # We let yfinance handle its own session now, our patch will catch it
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        return {
            'price': info.get('lastPrice', 0),
            'volume': info.get('last_volume', 0)
        }
    except Exception as e:
        logging.error(f"Failed light fetch for {ticker}: {e}")
        return {'price': 0, 'volume': 0}

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(2),
    retry=retry_if_exception_type((requests.exceptions.RequestException, Exception)),
    reraise=True
)
def get_option_chain_data(ticker, price, stock_vol):
    """Fetches the heavy option chains only for hot stocks."""
    stock = yf.Ticker(ticker)
    all_data = []
    
    try:
        options = list(stock.options)
        if not options:
            return pd.DataFrame()

        # Scan only next 5 expirations (most whale activity) to save API calls
        for exp in options[:5]:
            chain = stock.option_chain(exp)
            for side_name, side in [("calls", chain.calls), ("puts", chain.puts)]:
                if side.empty: continue
                side = side.copy()
                side['ticker'] = ticker
                side['exp'] = exp
                side['side'] = side_name
                side['dte'] = (pd.to_datetime(exp) - pd.Timestamp.now()).days
                side['notional'] = side['volume'] * side['lastPrice'].fillna(0) * 100
                side['vol_oi_ratio'] = side['volume'] / (side['openInterest'].replace(0, 1) + 1)
                side['underlying_price'] = price
                side['underlying_vol'] = stock_vol
                side['moneyness'] = abs(side['strike'] - price) / price * 100 if price > 0 else 0
                all_data.append(side)
            
            # Small delay between expirations to avoid burst blocking
            time.sleep(0.5)
            
    except Exception as e:
        logging.error(f"Option chain fetch failed for {ticker}: {e}")

    df = pd.concat(all_data) if all_data else pd.DataFrame()
    return df
