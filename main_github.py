import asyncio
import time
import pandas as pd
import random
import logging
from data_fetcher import get_stock_info, get_option_chain_data
from scanner import score_unusual, get_stock_heat
from alerts import send_alert
from historical_db import update_historical, is_alert_sent, mark_alert_sent, load_from_csv, save_to_csv, get_ticker_context
from config import WATCHLIST_FILE, MAX_TICKERS, MIN_STOCK_Z_SCORE
from massive_sync import sync_baselines

async def process_ticker_sequential(ticker):
    """Sequential worker function to avoid rate limiting."""
    try:
        logging.info(f"Scanning {ticker}...")
        
        # 1. Step 1: Light Fetch (Price & Volume)
        stock_data = get_stock_info(ticker)
        price = stock_data['price']
        stock_vol = stock_data['volume']
        
        if price == 0 or stock_vol == 0:
            logging.warning(f"No data for {ticker}. Skipping.")
            return []

        # 2. Step 2: Heat Check
        stock_z = get_stock_heat(ticker, stock_vol)
        
        # 3. Step 3: Conditional Heavy Fetch
        # We only fetch option chains if the stock is "Hot" OR it's a MegaCap/ETF we always want
        is_hot = stock_z > 1.0 # Lower threshold for the 'maybe' zone
        always_scan = ticker in ['SPY', 'QQQ', 'TSLA', 'NVDA', 'AAPL']
        
        if not is_hot and not always_scan:
            # logging.info(f"Ticker {ticker} is cold (Z: {stock_z:.1f}). Skipping options.")
            return []

        logging.info(f"Ticker {ticker} is HOT (Z: {stock_z:.1f}). Fetching option chains...")
        df = get_option_chain_data(ticker, price, stock_vol)

        if df.empty:
            return []

        # Save historical data
        update_historical(ticker, df)

        # Get historical context for AI reasoning
        context = get_ticker_context(ticker, days=2)

        # Check for whale trades
        flags = score_unusual(df, ticker, stock_z)

        trades_to_alert = []
        for _, trade in flags.iterrows():
            if not is_alert_sent(trade['contract']):
                trades_to_alert.append({'trade': trade.to_dict(), 'context': context})

        return trades_to_alert
    except Exception as e:
        logging.error(f"Error on {ticker}: {e}")
        return []

async def scan_cycle():
    # 1. Sync Baselines from Massive.com (Respects 5 req/min)
    sync_baselines()

    # 2. Load historical data into SQLite from CSV
    load_from_csv()

    watchlist = pd.read_csv(WATCHLIST_FILE)['ticker'].tolist()[:MAX_TICKERS]

    logging.info(f"Starting sequential scan for {len(watchlist)} tickers...")

    # 3. Process results and send alerts sequentially
    for ticker in watchlist:
        alerts_data = await process_ticker_sequential(ticker)
        
        for data in alerts_data:
            trade = data['trade']
            context = data['context']

            logging.info(f"Analyzing potential whale for {trade['ticker']}...")

            # send_alert now handles context-aware reasoning
            sent = await send_alert(trade, context)
            mark_alert_sent(trade['contract'])

            if sent:
                logging.info(f"Alert SENT for {trade['ticker']}!")
                await asyncio.sleep(1) 

        # 4. Mandatory delay between tickers to stay under Yahoo's radar
        # (3-5 seconds is safe for 150 tickers)
        time.sleep(random.uniform(3, 5))

    # 5. Export updated database back to CSV
    save_to_csv()

if __name__ == "__main__":
    logging.info("Starting FlowGod Whale Tracker (Safe Sequential Mode)")
    asyncio.run(scan_cycle())
    logging.info("Scan complete.")
