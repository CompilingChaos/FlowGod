import yfinance as yf
import pandas as pd
from datetime import datetime

def get_options_data(ticker):
    stock = yf.Ticker(ticker)
    try:
        price = stock.info.get('regularMarketPrice') or stock.fast_info.get('lastPrice', 0)
    except:
        price = 0
    
    all_data = []
    for exp in list(stock.options)[:10]:   # next 10 expirations
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
            side['moneyness'] = abs(side['strike'] - price) / price * 100 if price > 0 else 0
            all_data.append(side)
    
    df = pd.concat(all_data) if all_data else pd.DataFrame()
    return df, price
