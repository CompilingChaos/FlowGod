import yfinance as yf
import pandas as pd
import requests
import time
import logging
import re
from datetime import datetime
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from config import CLOUDFLARE_PROXY_URL

# --- Cloudflare Bridge Adapter ---
class CloudflareAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, proxy_url, *args, **kwargs):
        self.proxy_url = proxy_url.rstrip('/')
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        # Support both query1 and query2 subdomains
        if "finance.yahoo.com" in request.url:
            original_url = request.url
            # Match any queryX.finance.yahoo.com
            request.url = re.sub(r'https://query\d\.finance\.yahoo\.com', self.proxy_url, request.url)
            logging.debug(f"Bridging: {original_url} -> {request.url}")
        return super().send(request, **kwargs)

# Setup the Session with the Bridge
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

if CLOUDFLARE_PROXY_URL:
    adapter = CloudflareAdapter(CLOUDFLARE_PROXY_URL)
    # Mount for both possible subdomains
    session.mount("https://query1.finance.yahoo.com", adapter)
    session.mount("https://query2.finance.yahoo.com", adapter)
    logging.info(f"✅ Cloudflare Bridge ENABLED: {CLOUDFLARE_PROXY_URL}")
else:
    logging.error("❌ Cloudflare Bridge DISABLED: CLOUDFLARE_PROXY_URL not found in environment!")
# ---------------------------------

def get_stock_info(ticker):
    """Fetches just the stock price and volume (Fast/Light)."""
    try:
        stock = yf.Ticker(ticker, session=session)
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
    stock = yf.Ticker(ticker, session=session)
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
