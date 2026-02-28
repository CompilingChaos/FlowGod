import requests
import time
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from config import MASSIVE_API_KEY, WATCHLIST_FILE, BASELINE_DAYS
from historical_db import update_ticker_baseline

import yfinance as yf

# Persistent Session for yfinance to avoid rate limits
yf_session = requests.Session()
yf_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

def sync_baselines():
    if not MASSIVE_API_KEY:
        logging.error("No MASSIVE_API_KEY found. Skipping sync.")
        return

    try:
        watchlist = pd.read_csv(WATCHLIST_FILE)['ticker'].tolist()
    except Exception as e:
        logging.error(f"Failed to read watchlist: {e}")
        return

    logging.info(f"Starting Multi-Source Baseline Sync for {len(watchlist)} tickers...")
    
    # Massive.com Window (Shifted)
    end_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=63)).strftime('%Y-%m-%d') 

    for i, ticker in enumerate(watchlist):
        try:
            # OPTION 1: Non-US Ticker (Use yfinance as fallback)
            if "." in ticker:
                logging.info(f"Syncing non-US ticker {ticker} via yfinance fallback...")
                stock = yf.Ticker(ticker, session=yf_session)
                hist = stock.history(period="60d") 
                if not hist.empty and 'Volume' in hist:
                    volumes = hist['Volume'].tail(BASELINE_DAYS).tolist()
                    if len(volumes) > 5:
                        avg_vol = np.mean(volumes)
                        std_dev = np.std(volumes)
                        update_ticker_baseline(ticker, avg_vol, std_dev)
                        logging.info(f"Updated {ticker} (yfinance): Avg Vol {avg_vol:,.0f}")
                
                # Sleep even for yfinance to avoid GitHub Actions IP blocks
                time.sleep(5)
                continue

            # OPTION 2: US Ticker (Use Massive.com)
            url = f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}?adjusted=true&sort=desc&limit={BASELINE_DAYS}&apiKey={MASSIVE_API_KEY}"
            
            response = requests.get(url)
            data = response.json()

            if response.status_code == 200 and data.get('status') == 'OK' and 'results' in data:
                volumes = [day['v'] for day in data['results']]
                if len(volumes) > 5:
                    avg_vol = np.mean(volumes)
                    std_dev = np.std(volumes)
                    update_ticker_baseline(ticker, avg_vol, std_dev)
                    logging.info(f"Updated {ticker} (Massive): Avg Vol {avg_vol:,.0f}")
                else:
                    logging.warning(f"Not enough data for {ticker} (got {len(volumes)} days)")
            else:
                error_msg = data.get('error') or data.get('status') or "Unknown API Error"
                logging.error(f"Massive.com error for {ticker} (Status {response.status_code}): {error_msg}")

            # Rate Limit: 5 requests per minute for Massive.com
            if i < len(watchlist) - 1:
                time.sleep(13) 

        except Exception as e:
            logging.error(f"Sync failed for {ticker}: {e}")
            time.sleep(5)

if __name__ == "__main__":
    sync_baselines()
