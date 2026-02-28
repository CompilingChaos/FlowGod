import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# Persistent Session for connection reuse
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((requests.exceptions.RequestException, Exception)),
    reraise=True
)
def get_options_data(ticker):
    """Fetches options data with retries and session reuse."""
    stock = yf.Ticker(ticker, session=session)
    
    try:
        # Prefer fast_info for performance
        price = stock.fast_info.get('lastPrice', 0)
        stock_vol = stock.fast_info.get('last_volume', 0)
    except:
        price = 0
        stock_vol = 0
    
    all_data = []
    options = list(stock.options)
    if not options:
        return pd.DataFrame(), price, stock_vol

    for exp in options[:10]:   # next 10 expirations
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
    
    df = pd.concat(all_data) if all_data else pd.DataFrame()
    return df, price, stock_vol
