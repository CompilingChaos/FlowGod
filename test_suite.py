import asyncio
import logging
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from shadow_ingestion import ShadowDeepDive, run_deep_dive_analysis
from error_reporter import reporter
from data_fetcher import get_advanced_macro, get_sector_etf_performance, get_stock_info, get_sec_filings, get_market_regime, get_sector_divergence
from scanner import (
    calculate_greeks_vec, calculate_volatility_surface, 
    detect_microstructure_conviction, generate_system_verdict, 
    score_unusual, map_vanna_charm_exposures, map_gex_walls,
    process_results
)
from alerts import send_alert
from historical_db import (
    init_db, mark_alert_sent, get_rag_context, 
    update_trust_score, get_ticker_baseline,
    mark_alert_confirmed
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def run_ultimate_test_suite():
    logging.info("🚀 STARTING FULL-SPECTRUM FLOWGOD VALIDATION 🚀")

    # 1. MACRO & REGIME DATA INTEGRITY
    logging.info("\n--- STEP 1: DATA INGESTION (Macro & Regime) ---")
    macro = get_advanced_macro()
    regime = get_market_regime()
    logging.info(f"✅ Market Regime: {regime} (SPY: {macro['spy']}%)")
    
    sec_filings = get_sec_filings("AAPL")
    if sec_filings:
        logging.info(f"✅ SEC EDGAR: Successfully shadowed filings for AAPL.")

    # 2. SECTOR DIVERGENCE (HEGDE DETECTION)
    logging.info("\n--- STEP 2: CROSS-ASSET HEDGE DETECTION ---")
    divergence = get_sector_divergence("AAPL", "Technology")
    logging.info(f"✅ Sector Divergence Sensor: {divergence}")

    # 3. VECTORIZED QUANT ENGINE TEST
    logging.info("\n--- STEP 3: VECTORIZED QUANT ENGINE (BS-4D) ---")
    S = np.array([150.0, 150.0])
    K = np.array([155.0, 145.0])
    T = np.array([0.1, 0.1])
    sigma = np.array([0.3, 0.3])
    d, g, v, c, color = calculate_greeks_vec(S, K, T, 0.045, sigma, 'calls')
    logging.info(f"✅ Vectorized Greeks: Delta[0] {d[0]} | Gamma[0] {g[0]}")

    # 4. ADAPTIVE SCORER (REGIME WEIGHTS)
    logging.info("\n--- STEP 4: ADAPTIVE REGIME SCORING ---")
    mock_whale_df = pd.DataFrame([{
        'ticker': 'NVDA', 'contractSymbol': 'NVDA_PUT', 'side': 'puts', 'strike': 120.0,
        'exp': '2026-03-15', 'dte': 30, 'volume': 5000, 'openInterest': 100, 
        'impliedVolatility': 0.45, 'lastPrice': 2.50, 'bid': 2.45, 'ask': 2.50, 
        'underlying_price': 130.0, 'notional': 1250000, 'vol_oi_ratio': 50.0 
    }])
    
    # Test scoring in RISK_OFF regime
    results = score_unusual(mock_whale_df, 'NVDA', 2.0, 'Technology', regime="RISK_OFF")
    if not results.empty:
        score = results.iloc[0]['score']
        reason = results.iloc[0]['detection_reason']
        logging.info(f"✅ Adaptive Scorer (RISK_OFF): Score {score} | Reason: {reason}")

    # 5. SPREAD & CLUSTER LINKING
    logging.info("\n--- STEP 5: SPREAD & CLUSTER LINKING ---")
    mock_results = [
        {'ticker': 'AMD', 'exp': '2026-03-20', 'type': 'CALLS', 'strike': 150, 'volume': 5000, 'score': 90, 'contract': 'AMD1', 'notional': 100000},
        {'ticker': 'AMD', 'exp': '2026-03-20', 'type': 'CALLS', 'strike': 155, 'volume': 4900, 'score': 85, 'contract': 'AMD2', 'notional': 100000}
    ]
    final = process_results(mock_results, macro, {})
    if any("SPREAD" in f['type'] for f in final):
        logging.info("✅ Spread Detection: Successfully linked vertical legs.")

    # 6. SHADOW INGESTION
    logging.info("\n--- STEP 6: SHADOW INGESTION ---")
    shadow = ShadowDeepDive()
    triggers = shadow.get_trigger_tickers()
    logging.info(f"✅ Shadow Analysis complete. Found {len(triggers)} triggers.")

    # 7. LIVE TELEGRAM ALERT TEST
    logging.info("\n--- STEP 7: TELEGRAM & AI ANALYST CHAIN ---")
    test_trade = {
        'type': 'CALLS', 'underlying_price': 138.50, 'call_wall': 160.0, 'put_wall': 130.0,
        'vanna_exp': 850000, 'charm_exp': 120000, 'flip': 142.0, 'ticker': 'NVDA', 'strike': 150.0, 
        'exp': '2024-06-21', 'volume': 8500, 'oi': 1200, 'notional': 4420000, 'rel_vol': 15.2, 
        'premium': 5.20, 'delta': 0.48, 'gamma': 0.025, 'vanna': 0.12, 'charm': 0.05, 
        'gex': 1250000, 'score': 185, 'aggression': 'Aggressive (Ask) | SLINGSHOT', 
        'sector': 'AI', 'sec_signal': '🔥 CEO/Insider Just Bought', 'hype_z': 1.2, 'weekly_count': 4,
        'earnings_date': '2026-05-20', 'earnings_dte': 45, 'regime': regime, 'divergence': 'Relative Strength'
    }
    
    sent = await send_alert(test_trade, "PILLAR 1 & 3 VALIDATION: Market Awareness Active.", macro)
    if sent:
        logging.info("✨ SUCCESS: Adaptive alert dispatched!")
    else:
        logging.error("❌ TELEGRAM FAILURE.")

    logging.info("\n🏁 FULL-SPECTRUM VALIDATION COMPLETE 🏁")

if __name__ == "__main__":
    asyncio.run(run_ultimate_test_suite())
