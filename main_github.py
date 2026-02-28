import asyncio
import time
import pandas as pd
import random
import logging
import re
from data_fetcher import get_stock_info, get_option_chain_data, get_advanced_macro, get_contract_oi, get_sector_etf_performance, get_intraday_aggression
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
    """Sequential worker function."""
    try:
        logging.info(f"Scanning {ticker}...")
        stock_data = get_stock_info(ticker)
        price = stock_data['price']
        stock_vol = stock_data['volume']
        
        if price == 0 or stock_vol == 0: return []

        stock_z, sector = get_stock_heat(ticker, stock_vol)
        is_hot = stock_z > 1.0 
        always_scan = ticker in ['SPY', 'QQQ', 'TSLA', 'NVDA', 'AAPL']
        
        if not is_hot and not always_scan: return []

        # Tier-2: Get Intraday Candle for TRV and Dark Pool Proxies
        candle = get_intraday_aggression(ticker)
        
        # Tier-2: Pull deeper chain for GEX Wall mapping
        df = get_option_chain_data(ticker, price, stock_vol, full_chain=True)
        if df.empty: return []

        update_historical(ticker, df)
        context = get_ticker_context(ticker, days=2)

        # Scorer now handles Surface, GEX Walls, and TRV
        flags = score_unusual(df, ticker, stock_z, sector, candle)

        trades_to_alert = []
        for _, trade in flags.iterrows():
            if not is_alert_sent(trade['contract']):
                trades_to_alert.append({'trade': trade.to_dict(), 'context': context})
        return trades_to_alert
    except Exception as e:
        logging.error(f"Error on {ticker}: {e}")
        return []

async def verify_stickiness():
    unconfirmed = get_unconfirmed_alerts()
    if not unconfirmed: return
    logging.info(f"Verifying {len(unconfirmed)} past alerts...")
    for contract, yest_vol, yest_oi in unconfirmed:
        try:
            live_oi = get_contract_oi(contract)
            if live_oi == 0: continue 
            ticker_match = re.match(r'^([A-Z]+)', contract)
            if not ticker_match: continue
            ticker = ticker_match.group(1)
            oi_change = live_oi - yest_oi
            ratio = oi_change / yest_vol if yest_vol > 0 else 0
            if ratio >= 0.70:
                await send_confirmation_alert(ticker, contract, oi_change, ratio*100)
                update_trust_score(ticker, 0.15) 
                mark_alert_confirmed(contract, 1)
            elif ratio < 0.20:
                update_trust_score(ticker, -0.05) 
                mark_alert_confirmed(contract, -1)
            else: mark_alert_confirmed(contract, 2) 
        except: pass

async def scan_cycle():
    sync_baselines()
    load_from_csv()
    await verify_stickiness()
    
    macro = get_advanced_macro()
    sectors = get_sector_etf_performance()
    watchlist = pd.read_csv(WATCHLIST_FILE)['ticker'].tolist()[:MAX_TICKERS]
    
    all_raw_alerts = []
    for ticker in watchlist:
        alerts_data = await process_ticker_sequential(ticker)
        all_raw_alerts.extend(alerts_data)
        time.sleep(random.uniform(3, 5))

    # Correlation Scorer (Clusters & Multi-Leg)
    just_trades = [a['trade'] for a in all_raw_alerts]
    final_trades = process_results(just_trades, macro, sectors)

    for trade in final_trades:
        context = "No historical context."
        for a in all_raw_alerts:
            if a['trade']['ticker'] == trade['ticker']:
                context = a['context']
                break
        sent = await send_alert(trade, context, macro)
        mark_alert_sent(trade['contract'], ticker=trade['ticker'], trade_type=trade['type'], vol=trade['volume'], oi=trade['oi'], price=trade['premium'])
        if sent: await asyncio.sleep(1) 
    save_to_csv()

if __name__ == "__main__":
    asyncio.run(scan_cycle())
