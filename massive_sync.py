import requests
import time
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from config import MASSIVE_API_KEY, WATCHLIST_FILE, BASELINE_DAYS
from historical_db import update_ticker_baseline

def sync_baselines():
    if not MASSIVE_API_KEY:
        logging.error("No MASSIVE_API_KEY found. Skipping sync.")
        return

    try:
        watchlist = pd.read_csv(WATCHLIST_FILE)['ticker'].tolist()
    except Exception as e:
        logging.error(f"Failed to read watchlist: {e}")
        return

    logging.info(f"Starting Massive.com sync for {len(watchlist)} tickers (30-day window)...")
    
    # Shift end_date back by 3 days to avoid 'DELAYED' status on Massive Free Tier
    end_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=63)).strftime('%Y-%m-%d') 

    count = 0
    for ticker in watchlist:
        # Skip non-US tickers (containing dots like .DE, .MI) as Massive Free Tier doesn't support them
        if "." in ticker:
            logging.info(f"Skipping non-US ticker {ticker} (Massive Free Tier restriction)")
            continue

        try:
            # Massive.com Aggregates Endpoint
            url = f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}?adjusted=true&sort=desc&limit={BASELINE_DAYS}&apiKey={MASSIVE_API_KEY}"
            
            response = requests.get(url)
            data = response.json()

            if response.status_code == 200 and data.get('status') == 'OK' and 'results' in data:
                volumes = [day['v'] for day in data['results']]
                if len(volumes) > 5:
                    avg_vol = np.mean(volumes)
                    std_dev = np.std(volumes)
                    update_ticker_baseline(ticker, avg_vol, std_dev)
                    logging.info(f"Updated {ticker}: Avg Vol {avg_vol:,.0f}, Std Dev {std_dev:,.0f}")
                else:
                    logging.warning(f"Not enough data for {ticker} (got {len(volumes)} days)")
            else:
                error_msg = data.get('error') or data.get('status') or "Unknown API Error"
                logging.error(f"Massive.com error for {ticker} (Status {response.status_code}): {error_msg}")

            count += 1
            # Rate Limit: 5 requests per minute -> 12 seconds per request
            if count < len(watchlist):
                time.sleep(13) 

        except Exception as e:
            logging.error(f"Sync failed for {ticker}: {e}")
            time.sleep(13)

if __name__ == "__main__":
    sync_baselines()
