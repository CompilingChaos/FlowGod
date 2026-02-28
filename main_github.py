import asyncio
import time
import pandas as pd
import random
import logging
from data_fetcher import get_stock_info, get_option_chain_data, get_macro_context
from scanner import score_unusual, get_stock_heat, process_results
from alerts import send_alert
from historical_db import update_historical, is_alert_sent, mark_alert_sent, load_from_csv, save_to_csv, get_ticker_context
from config import WATCHLIST_FILE, MAX_TICKERS, MIN_STOCK_Z_SCORE
from massive_sync import sync_baselines

async def process_ticker_sequential(ticker):
    """Sequential worker function to avoid rate limiting."""
    try:
        logging.info(f"Scanning {ticker}...")
        
        # 1. Step 1: Light Fetch
        stock_data = get_stock_info(ticker)
        price = stock_data['price']
        stock_vol = stock_data['volume']
        
        if price == 0 or stock_vol == 0:
            return []

        # 2. Step 2: Heat Check (returns Z and Sector)
        stock_z, sector = get_stock_heat(ticker, stock_vol)
        
        # 3. Step 3: Conditional Heavy Fetch
        is_hot = stock_z > 1.0 
        always_scan = ticker in ['SPY', 'QQQ', 'TSLA', 'NVDA', 'AAPL']
        
        if not is_hot and not always_scan:
            return []

        logging.info(f"Ticker {ticker} is HOT (Z: {stock_z:.1f}). Fetching options...")
        df = get_option_chain_data(ticker, price, stock_vol)

        if df.empty:
            return []

        update_historical(ticker, df)
        context = get_ticker_context(ticker, days=2)

        # Check for whale trades
        flags = score_unusual(df, ticker, stock_z, sector)

        trades_to_alert = []
        for _, trade in flags.iterrows():
            if not is_alert_sent(trade['contract']):
                trades_to_alert.append({
                    'trade': trade.to_dict(), 
                    'context': context
                })

        return trades_to_alert
    except Exception as e:
        logging.error(f"Error on {ticker}: {e}")
        return []

async def scan_cycle():
    # 1. Pre-Scan Prep
    sync_baselines()
    load_from_csv()
    
    # 2. Global Macro Context
    macro = get_macro_context()
    logging.info(f"Macro Sentiment: {macro['sentiment']} (SPY: {macro['spy_pc']}%, VIX: {macro['vix_pc']}%)")

    watchlist = pd.read_csv(WATCHLIST_FILE)['ticker'].tolist()[:MAX_TICKERS]
    logging.info(f"Starting sequential scan for {len(watchlist)} tickers...")

    all_raw_alerts = []

    # 3. Collect results sequentially
    for ticker in watchlist:
        alerts_data = await process_ticker_sequential(ticker)
        all_raw_alerts.extend(alerts_data)
        # Mandatory delay to stay under Yahoo radar
        time.sleep(random.uniform(3, 5))

    # 4. Post-Process: Clustering & Sector Heat Mapping
    # We extract just the 'trade' dicts for processing
    just_trades = [a['trade'] for a in all_raw_alerts]
    final_trades = process_results(just_trades, macro)

    # 5. Send final consolidated alerts
    for trade in final_trades:
        # Re-link the context (finding the first match for that ticker)
        context = "No context available."
        for a in all_raw_alerts:
            if a['trade']['ticker'] == trade['ticker']:
                context = a['context']
                break

        logging.info(f"Analyzing high-conviction flow for {trade['ticker']}...")
        sent = await send_alert(trade, context, macro)
        mark_alert_sent(trade['contract'])

        if sent:
            logging.info(f"Alert SENT for {trade['ticker']}!")
            await asyncio.sleep(1) 

    # 6. Export updated database back to CSV
    save_to_csv()

if __name__ == "__main__":
    logging.info("Starting FlowGod Whale Tracker (Advanced Correlation Mode)")
    asyncio.run(scan_cycle())
    logging.info("Scan complete.")
