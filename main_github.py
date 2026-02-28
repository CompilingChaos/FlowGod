import asyncio
import time
import pandas as pd
import random
import logging
import re
from data_fetcher import get_stock_info, get_option_chain_data, get_macro_context, get_contract_oi
from scanner import score_unusual, get_stock_heat, process_results
from alerts import send_alert, send_confirmation_alert
from historical_db import (
    update_historical, is_alert_sent, mark_alert_sent, 
    load_from_csv, save_to_csv, get_ticker_context,
    get_unconfirmed_alerts, mark_alert_confirmed, update_trust_score,
    init_db
)
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

async def verify_stickiness():
    """Checks if yesterday's whales held their positions."""
    unconfirmed = get_unconfirmed_alerts()
    if not unconfirmed: return

    logging.info(f"Verifying stickiness for {len(unconfirmed)} past alerts...")
    
    for contract, timestamp in unconfirmed:
        try:
            # 1. Fetch current live OI
            live_oi = get_contract_oi(contract)
            if live_oi == 0: continue 

            # 2. Get historical data
            ticker_match = re.match(r'^([A-Z]+)', contract)
            if not ticker_match: continue
            ticker = ticker_match.group(1)
            
            conn = init_db()
            # Get last 2 records for this contract to see yesterday's stats
            hist = conn.execute("SELECT volume, oi FROM hist_vol_oi WHERE contract = ? ORDER BY date DESC LIMIT 2", (contract,)).fetchall()
            conn.close()

            if len(hist) < 2: continue
            
            yest_vol = hist[0][0]
            yest_oi = hist[1][1]
            oi_change = live_oi - yest_oi
            
            # 3. Calculate Stickiness %
            if yest_vol > 0:
                percentage = (oi_change / yest_vol) * 100
                if percentage > 70:
                    logging.info(f"✅ CONFIRMED: {contract} held {percentage:.1f}% overnight.")
                    await send_confirmation_alert(ticker, contract, oi_change, percentage)
                    update_trust_score(ticker, 0.1)
                    mark_alert_confirmed(contract, 1)
                elif percentage < 10:
                    logging.info(f"❌ FADED: {contract} only held {percentage:.1f}%.")
                    update_trust_score(ticker, -0.05)
                    mark_alert_confirmed(contract, -1)
                else:
                    mark_alert_confirmed(contract, 2) # Partial
        except Exception as e:
            logging.error(f"Stickiness check failed for {contract}: {e}")

async def scan_cycle():
    # 1. Pre-Scan Prep
    sync_baselines()
    load_from_csv()
    
    # 2. Stickiness Verification
    await verify_stickiness()
    
    # 3. Global Macro Context
    macro = get_macro_context()
    logging.info(f"Macro Sentiment: {macro['sentiment']} (SPY: {macro['spy_pc']}%, VIX: {macro['vix_pc']}%)")

    watchlist = pd.read_csv(WATCHLIST_FILE)['ticker'].tolist()[:MAX_TICKERS]
    logging.info(f"Starting sequential scan for {len(watchlist)} tickers...")

    all_raw_alerts = []

    # 4. Collect results sequentially
    for ticker in watchlist:
        alerts_data = await process_ticker_sequential(ticker)
        all_raw_alerts.extend(alerts_data)
        time.sleep(random.uniform(3, 5))

    # 5. Post-Process
    just_trades = [a['trade'] for a in all_raw_alerts]
    final_trades = process_results(just_trades, macro)

    # 6. Send Alerts
    for trade in final_trades:
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

    save_to_csv()

if __name__ == "__main__":
    logging.info("Starting FlowGod Whale Tracker (Advanced Correlation Mode)")
    asyncio.run(scan_cycle())
    logging.info("Scan complete.")
