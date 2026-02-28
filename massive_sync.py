import requests
import time
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from config import MASSIVE_API_KEY, ALPHA_VANTAGE_API_KEY, WATCHLIST_FILE, BASELINE_DAYS
from historical_db import update_ticker_baseline, needs_baseline_update

import yfinance as yf

# Persistent Session for yfinance
yf_session = requests.Session()
yf_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

def sync_baselines():
    try:
        watchlist = pd.read_csv(WATCHLIST_FILE)['ticker'].tolist()
    except Exception as e:
        logging.error(f"Failed to read watchlist: {e}")
        return

    # Check which tickers actually need updating
    tickers_to_sync = [t for t in watchlist if needs_baseline_update(t)]
    
    if not tickers_to_sync:
        logging.info("All ticker baselines are up to date for today. Skipping sync.")
        return

    logging.info(f"Syncing {len(tickers_to_sync)}/{len(watchlist)} tickers (Once-per-day logic)...")
    
    # Massive.com Window (Shifted back 3 days for free tier)
    end_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=63)).strftime('%Y-%m-%d') 

    for i, ticker in enumerate(tickers_to_sync):
        try:
            # OPTION 1: Non-US Ticker (Use Alpha Vantage)
            if "." in ticker:
                if not ALPHA_VANTAGE_API_KEY:
                    logging.warning(f"No ALPHA_VANTAGE_API_KEY for {ticker}. Skipping.")
                    continue

                logging.info(f"Syncing non-US ticker {ticker} via Alpha Vantage...")
                url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
                
                response = requests.get(url)
                data = response.json()

                if "Time Series (Daily)" in data:
                    time_series = data["Time Series (Daily)"]
                    volumes = [int(v['5. volume']) for k, v in list(time_series.items())[:BASELINE_DAYS]]
                    
                    if len(volumes) > 5:
                        avg_vol = np.mean(volumes)
                        std_dev = np.std(volumes)
                        # Fetch sector info
                        sector = "Unknown"
                        try:
                            sector = yf.Ticker(ticker, session=yf_session).info.get('sector', 'Unknown')
                        except: pass
                        update_ticker_baseline(ticker, avg_vol, std_dev, sector)
                        logging.info(f"Updated {ticker} (AlphaV): Avg Vol {avg_vol:,.0f}, Sector: {sector}")
                    else:
                        logging.warning(f"Not enough data for {ticker} (AlphaV)")
                else:
                    err = data.get("Note") or data.get("Error Message") or f"Unknown AlphaV Error: {data}"
                    logging.error(f"Alpha Vantage failed for {ticker}: {err}")
                
                time.sleep(15)
                continue

            # OPTION 2: US Ticker (Use Massive.com)
            if not MASSIVE_API_KEY:
                logging.warning(f"No MASSIVE_API_KEY for {ticker}. Skipping.")
                continue

            url = f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}?adjusted=true&sort=desc&limit={BASELINE_DAYS}&apiKey={MASSIVE_API_KEY}"
            
            response = requests.get(url)
            data = response.json()

            if response.status_code == 200 and data.get('status') == 'OK':
                if 'results' in data and len(data['results']) > 0:
                    volumes = [day['v'] for day in data['results']]
                    if len(volumes) > 5:
                        avg_vol = np.mean(volumes)
                        std_dev = np.std(volumes)
                        # Fetch sector info
                        sector = "Unknown"
                        try:
                            sector = yf.Ticker(ticker, session=yf_session).info.get('sector', 'Unknown')
                        except: pass
                        update_ticker_baseline(ticker, avg_vol, std_dev, sector)
                        logging.info(f"Updated {ticker} (Massive): Avg Vol {avg_vol:,.0f}, Sector: {sector}")
                    else:
                        logging.warning(f"Not enough data for {ticker} (got {len(volumes)} days)")
                else:
                    logging.warning(f"Massive.com returned OK but no results for {ticker} (Check if ticker is active)")
            else:
                error_msg = data.get('error') or data.get('status') or "Unknown Massive Error"
                logging.error(f"Massive.com error for {ticker} (Status {response.status_code}): {error_msg}")

            if i < len(tickers_to_sync) - 1:
                time.sleep(13) 

        except Exception as e:
            logging.error(f"Sync failed for {ticker}: {e}")
            time.sleep(5)

if __name__ == "__main__":
    sync_baselines()
