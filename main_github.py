import asyncio
import time
import pandas as pd
from data_fetcher import get_options_data
from scanner import score_unusual
from alerts import send_alert
from historical_db import update_historical
from config import WATCHLIST_FILE, MAX_TICKERS

async def scan_cycle():
    watchlist = pd.read_csv(WATCHLIST_FILE)['ticker'].tolist()[:MAX_TICKERS]
    for ticker in watchlist:
        try:
            print(f"Scanning {ticker}...")
            df, _ = get_options_data(ticker)
            update_historical(ticker, df)
            flags = score_unusual(df, ticker)
            for _, trade in flags.iterrows():
                print(f"Alert found for {ticker}!")
                await send_alert(trade.to_dict())
            time.sleep(2)  # Delay to avoid rate limits
        except Exception as e:
            print(f"Error on {ticker}: {e}")

if __name__ == "__main__":
    print("Starting FlowGod Whale Tracker (GitHub Actions Mode)")
    asyncio.run(scan_cycle())
    print("Scan complete.")
