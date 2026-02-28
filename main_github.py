import asyncio
import time
import pandas as pd
import concurrent.futures
import random
import logging
from data_fetcher import get_options_data
from scanner import score_unusual
from alerts import send_alert
from historical_db import update_historical, is_alert_sent, mark_alert_sent, load_from_csv, save_to_csv, get_ticker_context
from config import WATCHLIST_FILE, MAX_TICKERS
from massive_sync import sync_baselines

def process_ticker(ticker):
    """Worker function for parallel scanning."""
    try:
        # Small random delay (jitter) to avoid burst-pattern detection
        time.sleep(random.uniform(0.5, 1.5))

        logging.info(f"Scanning {ticker}...")
        df, price, stock_vol = get_options_data(ticker)

        # Save historical data
        update_historical(ticker, df)

        # Get historical context for AI reasoning
        context = get_ticker_context(ticker, days=2)

        # Check for whale trades
        flags = score_unusual(df, ticker)

        trades_to_alert = []
        for _, trade in flags.iterrows():
            if not is_alert_sent(trade['contract']):
                trades_to_alert.append({'trade': trade.to_dict(), 'context': context})

        return ticker, trades_to_alert
    except Exception as e:
        logging.error(f"Error on {ticker}: {e}")
        return ticker, []

async def scan_cycle():
    # 1. Sync Baselines from Massive.com (Respects 5 req/min)
    sync_baselines()

    # 2. Load historical data into SQLite from CSV
    load_from_csv()

    watchlist = pd.read_csv(WATCHLIST_FILE)['ticker'].tolist()[:MAX_TICKERS]

    logging.info(f"Starting parallel scan for {len(watchlist)} tickers...")

    # 3. Run parallel scanning using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_ticker, watchlist))

    # 4. Process results and send alerts sequentially
    for ticker, alerts_data in results:
        for data in alerts_data:
            trade = data['trade']
            context = data['context']

            logging.info(f"Analyzing potential whale for {ticker}...")

            # send_alert now handles context-aware reasoning
            sent = await send_alert(trade, context)

            mark_alert_sent(trade['contract'])

            if sent:
                logging.info(f"Alert SENT for {ticker}!")
                await asyncio.sleep(1) # Small delay between Telegram messages

            
    # 5. Export updated database back to CSV
    save_to_csv()

if __name__ == "__main__":
    logging.info("Starting FlowGod Whale Tracker (Parallel GitHub Actions Mode)")
    asyncio.run(scan_cycle())
    logging.info("Scan complete.")
