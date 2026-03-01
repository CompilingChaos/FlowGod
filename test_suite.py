import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from shadow_ingestion import ShadowDeepDive, run_deep_dive_analysis
from error_reporter import reporter
from data_fetcher import get_advanced_macro, get_sector_etf_performance, get_stock_info, get_sec_filings
from scanner import (
    calculate_greeks_vec, calculate_volatility_surface, 
    detect_microstructure_conviction, generate_system_verdict, 
    score_unusual, map_vanna_charm_exposures
)
from alerts import send_alert

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def run_ultimate_test_suite():
    logging.info("🚀 STARTING THE ULTIMATE FLOWGOD VALIDATION SUITE 🚀")

    # 1. MACRO & SEC DATA INTEGRITY
    logging.info("\n--- STEP 1: DATA INGESTION (Macro & SEC) ---")
    macro = get_advanced_macro()
    logging.info(f"✅ Macro Sentiment: {macro['sentiment']} (SPY: {macro['spy']}%)")
    
    sec_filings = get_sec_filings("AAPL")
    if sec_filings:
        logging.info(f"✅ SEC EDGAR: Successfully shadowed {len(sec_filings)} filings for AAPL.")
    else:
        logging.warning("⚠️ SEC EDGAR: No filings found for AAPL (Check compliance/UA).")

    # 2. VECTORIZED QUANT ENGINE TEST
    logging.info("\n--- STEP 2: VECTORIZED QUANT ENGINE (BS-4D) ---")
    S = np.array([150.0, 150.0])
    K = np.array([155.0, 145.0])
    T = np.array([0.1, 0.1])
    sigma = np.array([0.3, 0.3])
    
    d, g, v, c, color = calculate_greeks_vec(S, K, T, 0.045, sigma, 'calls')
    logging.info(f"✅ Vectorized Greeks: Delta[0] {d[0]} | Gamma[0] {g[0]} | Vanna[0] {v[0]}")

    # 3. VANNA/CHARM EXPOSURE TEST
    logging.info("\n--- STEP 3: 3D EXPOSURE MAPPING (Vanna/Charm) ---")
    mock_df = pd.DataFrame([{
        'side': 'calls', 'underlying_price': 150.0, 'strike': 155.0, 
        'vanna': 0.12, 'charm': 0.05, 'openInterest': 1000, 'dte': 10
    }])
    v_exp, c_exp = map_vanna_charm_exposures(mock_df)
    logging.info(f"✅ Exposure Mapping: Vanna Exp ${v_exp:,.0f} | Charm Exp {c_exp:,.0f}")

    # 4. PELOSI & GHOST FILING SCENARIO
    logging.info("\n--- STEP 4: INSIDER & GHOST FILING LOGIC ---")
    mock_whale_df = pd.DataFrame([{
        'ticker': 'PLTR', 'contractSymbol': 'PLTR_CALL', 'side': 'calls', 'strike': 25.0,
        'exp': '2026-03-15', 'dte': 30, 'volume': 5000, 'openInterest': 100, 
        'impliedVolatility': 0.45, 'lastPrice': 1.50, 'bid': 1.45, 'ask': 1.50, 
        'underlying_price': 24.0, 'notional': 750000, 'vol_oi_ratio': 50.0 
    }])
    
    # Test with Pelosi + SEC Ghost Echo
    results = score_unusual(
        mock_whale_df, 'PLTR', 3.0, 'Technology', 
        congress_tickers=['PLTR']
    )
    
    if not results.empty:
        reason = results.iloc[0]['detection_reason']
        logging.info(f"✅ Pelosi/SEC Scorer: {reason}")
    else:
        logging.warning("⚠️ Pelosi Scorer: Logic skipped or thresholds not met.")

    # 5. LIVE TELEGRAM ALERT TEST
    logging.info("\n--- STEP 5: FULL ALERT CHAIN & AI ANALYST ---")
    test_trade = {
        'type': 'CALLS', 'underlying_price': 138.50, 'call_wall': 160.0, 'put_wall': 130.0,
        'vanna_exp': 850000, 'charm_exp': 120000, 'flip': 142.0,
        'skew': -0.06, 'bias': 'BULLISH', 'ticker': 'NVDA', 'strike': 150.0, 'exp': '2024-06-21',
        'volume': 8500, 'oi': 1200, 'notional': 4420000, 'rel_vol': 15.2, 'premium': 5.20,
        'delta': 0.48, 'gamma': 0.025, 'vanna': 0.12, 'charm': 0.05, 'gex': 1250000,
        'score': 185, 'aggression': 'Aggressive (Ask) | SLINGSHOT', 'sector': 'AI',
        'sec_signal': 'GHOST ECHO (Form 4)', 'hype_z': 1.2, 'weekly_count': 4,
        'earnings_date': '2026-05-20', 'earnings_dte': 45
    }
    
    logging.info("📡 Dispatching TIER-4 VALIDATION ALERT to Telegram...")
    sent = await send_alert(test_trade, "ULTIMATE TEST: Verifying Tier-4 SEC & Quant Metrics.", macro)

    if sent:
        logging.info("✨ SUCCESS: The validation alert is on its way!")
    else:
        logging.error("❌ TELEGRAM FAILURE. Check your keys.")

    logging.info("\n🏁 ULTIMATE VALIDATION COMPLETE 🏁")

if __name__ == "__main__":
    asyncio.run(run_ultimate_test_suite())
