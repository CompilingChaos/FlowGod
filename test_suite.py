import asyncio
import logging
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from shadow_ingestion import ShadowDeepDive, run_deep_dive_analysis
from error_reporter import reporter
from data_fetcher import get_advanced_macro, get_sector_etf_performance, get_stock_info, get_sec_filings
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

    # 1. MACRO & SEC DATA INTEGRITY
    logging.info("\n--- STEP 1: DATA INGESTION (Macro & SEC) ---")
    macro = get_advanced_macro()
    logging.info(f"✅ Macro Sentiment: {macro['sentiment']} (SPY: {macro['spy']}%)")
    
    sec_filings = get_sec_filings("AAPL")
    if sec_filings:
        logging.info(f"✅ SEC EDGAR: Successfully shadowed {len(sec_filings)} filings for AAPL.")
    else:
        logging.warning("⚠️ SEC EDGAR: No filings found for AAPL.")

    # 2. VECTORIZED QUANT ENGINE TEST
    logging.info("\n--- STEP 2: VECTORIZED QUANT ENGINE (BS-4D) ---")
    S = np.array([150.0, 150.0])
    K = np.array([155.0, 145.0])
    T = np.array([0.1, 0.1])
    sigma = np.array([0.3, 0.3])
    d, g, v, c, color = calculate_greeks_vec(S, K, T, 0.045, sigma, 'calls')
    logging.info(f"✅ Vectorized Greeks: Delta[0] {d[0]} | Gamma[0] {g[0]}")

    # 3. GEX 2.0 & VANNA/CHARM EXPOSURES
    logging.info("\n--- STEP 3: GEX 2.0 & 3D EXPOSURES ---")
    mock_df = pd.DataFrame([
        {'side': 'calls', 'underlying_price': 100.0, 'strike': 105.0, 'gamma': 0.05, 'openInterest': 1000, 'vanna': 0.1, 'charm': 0.02, 'dte': 5},
        {'side': 'puts', 'underlying_price': 100.0, 'strike': 95.0, 'gamma': 0.05, 'openInterest': 1000, 'vanna': 0.1, 'charm': -0.02, 'dte': 5}
    ])
    call_wall, put_wall, flip = map_gex_walls(mock_df)
    v_exp, c_exp = map_vanna_charm_exposures(mock_df)
    logging.info(f"✅ GEX Walls: Call ${call_wall} | Put ${put_wall} | Flip ${flip}")
    logging.info(f"✅ Vanna/Charm: Vanna Exp ${v_exp:,.0f} | Charm Exp {c_exp:,.0f}")

    # 4. SPREAD & CLUSTER LINKING
    logging.info("\n--- STEP 4: SPREAD & CLUSTER LINKING ---")
    mock_results = [
        {'ticker': 'AMD', 'exp': '2026-03-20', 'type': 'CALLS', 'strike': 150, 'volume': 5000, 'score': 90, 'contractSymbol': 'AMD1', 'contract': 'AMD1', 'notional': 100000},
        {'ticker': 'AMD', 'exp': '2026-03-20', 'type': 'CALLS', 'strike': 155, 'volume': 4900, 'score': 85, 'contractSymbol': 'AMD2', 'contract': 'AMD2', 'notional': 100000},
        {'ticker': 'TSLA', 'exp': '2026-03-20', 'type': 'PUTS', 'strike': 200, 'volume': 1000, 'score': 80, 'contractSymbol': 'TSLA1', 'contract': 'TSLA1', 'notional': 50000},
        {'ticker': 'TSLA', 'exp': '2026-03-20', 'type': 'PUTS', 'strike': 205, 'volume': 1100, 'score': 82, 'contractSymbol': 'TSLA2', 'contract': 'TSLA2', 'notional': 50000},
        {'ticker': 'TSLA', 'exp': '2026-03-20', 'type': 'PUTS', 'strike': 210, 'volume': 1050, 'score': 81, 'contractSymbol': 'TSLA3', 'contract': 'TSLA3', 'notional': 50000}
    ]
    final = process_results(mock_results, macro, {})
    types = [f['type'] for f in final]
    if any("SPREAD" in t for t in types):
        logging.info("✅ Spread Detection: Successfully linked vertical legs.")
    if any("CLUSTER" in t for t in types):
        logging.info("✅ Cluster Detection: Successfully identified TSLA Put Cluster.")

    # 5. SHADOW INGESTION CONNECTIVITY
    logging.info("\n--- STEP 5: SHADOW INGESTION CONNECTIVITY ---")
    shadow = ShadowDeepDive()
    triggers = shadow.get_trigger_tickers()
    if triggers:
        logging.info(f"✅ Shadow Success: Found {len(triggers)} trigger tickers.")
    else:
        logging.warning("⚠️ Shadow Notice: No active triggers found (Market closed).")

    # 6. DATABASE RAG & STICKINESS
    logging.info("\n--- STEP 6: DB RAG & STICKINESS LOGIC ---")
    init_db()
    mark_alert_sent("TEST_CONTRACT", ticker="TEST", trade_type="CALLS", vol=1000, oi=500, price=2.5)
    rag = get_rag_context("TEST", "CALLS")
    logging.info(f"✅ RAG Memory: {rag}")
    
    update_trust_score("TEST", 0.5)
    baseline = get_ticker_baseline("TEST")
    if baseline and baseline['trust_score'] >= 1.5:
        logging.info("✅ Trust Score: Successfully updated.")
    
    # 7. COMPLEX MICROSTRUCTURE (SLINGSHOT)
    logging.info("\n--- STEP 7: SLINGSHOT SCORER VALIDATION ---")
    mock_sling_df = pd.DataFrame([{
        'ticker': 'NVDA', 'contractSymbol': 'NVDA_CALL', 'side': 'calls', 'strike': 150.0,
        'exp': '2026-03-15', 'dte': 30, 'volume': 5000, 'openInterest': 100, 
        'impliedVolatility': 0.45, 'lastPrice': 5.50, 'bid': 5.45, 'ask': 5.50, 
        'underlying_price': 140.0, 'notional': 2750000, 'vol_oi_ratio': 50.0 
    }])
    mock_sling_df['vanna'] = 5.0 
    results = score_unusual(mock_sling_df, 'NVDA', 2.5, 'Technology')
    if not results.empty and 'SLINGSHOT' in results.iloc[0]['detection_reason']:
        logging.info("✅ Scorer: Vanna Slingshot bonus applied.")

    # 8. LIVE TELEGRAM ALERT TEST
    logging.info("\n--- STEP 8: TELEGRAM & AI ANALYST CHAIN ---")
    test_trade = {
        'type': 'CALLS', 'underlying_price': 138.50, 'call_wall': 160.0, 'put_wall': 130.0,
        'vanna_exp': 850000, 'charm_exp': 120000, 'flip': 142.0, 'ticker': 'NVDA', 'strike': 150.0, 
        'exp': '2024-06-21', 'volume': 8500, 'oi': 1200, 'notional': 4420000, 'rel_vol': 15.2, 
        'premium': 5.20, 'delta': 0.48, 'gamma': 0.025, 'vanna': 0.12, 'charm': 0.05, 
        'score': 185, 'aggression': 'Aggressive (Ask) | SLINGSHOT', 
        'sector': 'AI', 'sec_signal': '🔥 CEO/Insider Just Bought', 'hype_z': 1.2, 'weekly_count': 4,
        'earnings_date': '2026-05-20', 'earnings_dte': 45
        }
    
    sent = await send_alert(test_trade, "FULL SYSTEM VALIDATION: Tier-4 confirmed.", macro)
    if sent:
        logging.info("✨ SUCCESS: Validation alert dispatched!")
    else:
        logging.error("❌ TELEGRAM FAILURE (Expected if keys are missing locally).")

    logging.info("\n🏁 FULL-SPECTRUM VALIDATION COMPLETE 🏁")

if __name__ == "__main__":
    asyncio.run(run_ultimate_test_suite())
