import asyncio
import time
import pandas as pd
import random
import logging
import re
from data_fetcher import get_stock_info, get_option_chain_data, get_advanced_macro, get_contract_oi, get_sector_etf_performance, get_intraday_aggression, get_social_velocity
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
from bot_listener import harvest_saved_trades
from occ_auditor import audit_clearinghouse
from shadow_ingestion import ShadowDeepDive, run_deep_dive_analysis
from error_reporter import reporter

async def process_ticker_sequential(ticker, sector_from_csv, is_deep_dive=False):
    """Sequential worker function."""
    try:
        logging.info(f"Scanning {ticker} ({sector_from_csv})...")
        stock_data = get_stock_info(ticker)
        price = stock_data['price']
        stock_vol = stock_data['volume']
        if price == 0 or stock_vol == 0: return []

        stock_z, sector_from_db, earnings_date = get_stock_heat(ticker, stock_vol)
        sector = sector_from_csv if sector_from_csv != "Unknown" else sector_from_db
        
        # Deep Dive bypasses Z-Score threshold
        if not (stock_z > 1.0 or is_deep_dive or ticker in ['SPY', 'QQQ', 'TSLA', 'NVDA', 'AAPL']): 
            return []

        logging.info(f"Ticker {ticker} is {'SHADOW TRIGGERED' if is_deep_dive else 'HOT'} (Z: {stock_z:.1f}). Fetching options...")
        candle = get_intraday_aggression(ticker)
        df = get_option_chain_data(ticker, price, stock_vol, full_chain=True)
        if df.empty: return []

        # Tier-3: Social Sentiment Fusion
        social_vel = get_social_velocity(ticker)

        update_historical(ticker, df)
        context = get_ticker_context(ticker, days=2)

        # Scorer now handles Surface, GEX Walls, TRV, Social Hype, and Earnings
        flags = score_unusual(df, ticker, stock_z, sector, candle, social_vel, earnings_date)

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
    logging.info(f"Verifying stickiness for {len(unconfirmed)} past alerts...")
    for contract, yest_vol, yest_oi in unconfirmed:
        try:
            live_oi = get_contract_oi(contract)
            if live_oi == 0: continue 
            ticker_match = re.match(r'^([A-Z]+)', contract)
            if not ticker_match: continue
            ticker = ticker_match.group(1)
            ratio = (live_oi - yest_oi) / yest_vol if yest_vol > 0 else 0
            if ratio >= 0.70:
                await send_confirmation_alert(ticker, contract, live_oi-yest_oi, ratio*100)
                update_trust_score(ticker, 0.15) 
                mark_alert_confirmed(contract, 1)
            elif ratio < 0.20:
                update_trust_score(ticker, -0.05) 
                mark_alert_confirmed(contract, -1)
            else: mark_alert_confirmed(contract, 2) 
        except: pass

async def scan_cycle():
    # 1. Institutional Audit (Nightly OCC Check)
    audit_clearinghouse()

    # 2. Pre-Scan Prep & Harvesting
    sync_baselines()
    load_from_csv()
    harvest_saved_trades()
    
    # 3. Stickiness Verification
    await verify_stickiness()
    
    # 4. Market Context
    macro = get_advanced_macro()
    sectors = get_sector_etf_performance()
    
    # 5. Tier-3 Shadow Intelligence Trigger
    shadow = ShadowDeepDive()
    trigger_tickers = shadow.get_trigger_tickers()
    
    watchlist_df = pd.read_csv(WATCHLIST_FILE).head(MAX_TICKERS)
    scan_list = []
    for _, row in watchlist_df.iterrows():
        scan_list.append({'ticker': row['ticker'], 'sector': row['sector'], 'is_deep': False})
    
    # Inject Trigger Tickers at the front
    for t in trigger_tickers:
        if t not in [s['ticker'] for s in scan_list]:
            scan_list.insert(0, {'ticker': t, 'sector': 'Unknown', 'is_deep': True})
        else:
            # Upgrade existing ticker to Deep Dive
            for s in scan_list:
                if s['ticker'] == t: s['is_deep'] = True
    
    all_raw_alerts = []
    for item in scan_list:
        alerts_data = await process_ticker_sequential(item['ticker'], item['sector'], is_deep_dive=item['is_deep'])
        all_raw_alerts.extend(alerts_data)
        time.sleep(random.uniform(3, 5))

    just_trades = [a['trade'] for a in all_raw_alerts]
    final_trades = process_results(just_trades, macro, sectors)

    for trade in final_trades:
        context = "No historical context."
        is_shadow = False
        for a in all_raw_alerts:
            if a['trade']['ticker'] == trade['ticker']:
                context = a['context']
                # Check if this ticker was originally deep-dive triggered
                for item in scan_list:
                    if item['ticker'] == trade['ticker'] and item['is_deep']:
                        is_shadow = True
                        break
                break
        sent = await send_alert(trade, context, macro, is_shadow=is_shadow)
        mark_alert_sent(trade['contract'], ticker=trade['ticker'], trade_type=trade['type'], vol=trade['volume'], oi=trade['oi'], price=trade['premium'])
        if sent: await asyncio.sleep(1) 
    save_to_csv()

if __name__ == "__main__":
    try:
        asyncio.run(scan_cycle())
    except Exception as e:
        logging.error(f"FATAL: Scan cycle collapsed: {e}")
        asyncio.run(reporter.report_critical_error("MAIN_CYCLE", e, "Global crash in scan_cycle entry point."))
