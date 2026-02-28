import requests
import time
import pandas as pd
import numpy as np
import logging
import io
from datetime import datetime, timedelta
from config import MASSIVE_API_KEY, ALPHA_VANTAGE_API_KEY, WATCHLIST_FILE, BASELINE_DAYS
from historical_db import update_ticker_baseline, needs_baseline_update
from data_fetcher import get_social_velocity

import yfinance as yf

# Persistent Session for yfinance
yf_session = requests.Session()
yf_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

def fetch_earnings_calendar():
    """Fetches the 3-month earnings calendar from Alpha Vantage."""
    if not ALPHA_VANTAGE_API_KEY:
        return {}
    
    url = f"https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&horizon=3month&apikey={ALPHA_VANTAGE_API_KEY}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            # Create a mapping of ticker -> reportDate
            return dict(zip(df['symbol'], df['reportDate']))
    except Exception as e:
        logging.error(f"Failed to fetch earnings calendar: {e}")
    return {}

def sync_baselines():
    try:
        watchlist_df = pd.read_csv(WATCHLIST_FILE)
        watchlist = watchlist_df['ticker'].tolist()
        ticker_to_sector = dict(zip(watchlist_df['ticker'], watchlist_df['sector']))
    except Exception as e:
        logging.error(f"Failed to read watchlist: {e}")
        return

    # Fetch fresh earnings data for the whole market (1 call)
    earnings_map = fetch_earnings_calendar()

    tickers_to_sync = [t for t in watchlist if needs_baseline_update(t)]
    if not tickers_to_sync:
        logging.info("All ticker baselines up to date.")
        return

    logging.info(f"Syncing {len(tickers_to_sync)} tickers (Social + Volume + Earnings)...")
    end_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=63)).strftime('%Y-%m-%d') 

    for i, ticker in enumerate(tickers_to_sync):
        try:
            sector = ticker_to_sector.get(ticker, "Unknown")
            social_vel = get_social_velocity(ticker)
            earnings_date = earnings_map.get(ticker)
            
            # OPTION 1: Non-US Ticker (Alpha Vantage)
            if "." in ticker:
                if not ALPHA_VANTAGE_API_KEY: continue
                url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
                response = requests.get(url)
                data = response.json()
                if "Time Series (Daily)" in data:
                    time_series = data["Time Series (Daily)"]
                    volumes = [int(v['5. volume']) for k, v in list(time_series.items())[:BASELINE_DAYS]]
                    if len(volumes) > 5:
                        avg_vol = np.mean(volumes)
                        std_dev = np.std(volumes)
                        if sector == "Unknown":
                            try: sector = yf.Ticker(ticker, session=yf_session).info.get('sector', 'Unknown')
                            except: pass
                        update_ticker_baseline(ticker, avg_vol, std_dev, sector, social_vel, earnings_date)
                        logging.info(f"Updated {ticker} (AlphaV) | Social: {social_vel} | Earnings: {earnings_date}")
                time.sleep(15)
                continue

            # OPTION 2: US Ticker (Massive.com)
            if not MASSIVE_API_KEY: continue
            url = f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}?adjusted=true&sort=desc&limit={BASELINE_DAYS}&apiKey={MASSIVE_API_KEY}"
            response = requests.get(url)
            data = response.json()
            if response.status_code == 200 and data.get('status') == 'OK':
                if 'results' in data and len(data['results']) > 0:
                    volumes = [day['v'] for day in data['results']]
                    if len(volumes) > 5:
                        avg_vol = np.mean(volumes)
                        std_dev = np.std(volumes)
                        if sector == "Unknown":
                            try: sector = yf.Ticker(ticker, session=yf_session).info.get('sector', 'Unknown')
                            except: pass
                        update_ticker_baseline(ticker, avg_vol, std_dev, sector, social_vel, earnings_date)
                        logging.info(f"Updated {ticker} (Massive) | Social: {social_vel} | Earnings: {earnings_date}")
            if i < len(tickers_to_sync) - 1: time.sleep(13) 
        except Exception as e:
            logging.error(f"Sync failed for {ticker}: {e}")
            time.sleep(5)

if __name__ == "__main__":
    sync_baselines()
