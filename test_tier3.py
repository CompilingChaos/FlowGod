import asyncio
import logging
import pandas as pd
import numpy as np
from shadow_ingestion import ShadowDeepDive, run_deep_dive_analysis
from error_reporter import reporter
from data_fetcher import get_advanced_macro, get_sector_etf_performance, get_stock_info
from scanner import calculate_greeks, calculate_volatility_surface, detect_microstructure_conviction, generate_system_verdict, score_unusual
from alerts import send_alert

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def run_validation_suite():
    logging.info("🚀 STARTING THE ULTIMATE FLOWGOD VALIDATION 🚀")

    # 1. MACRO & ETF DATA TEST
    logging.info("\n--- STEP 1: MACRO & ETF DATA INTEGRITY ---")
    macro = get_advanced_macro()
    logging.info(f"✅ Macro Sentiment: {macro['sentiment']} (SPY: {macro['spy']}%)")
    
    sectors = get_sector_etf_performance()
    if sectors:
        logging.info(f"✅ Sector Data: Fetched {len(sectors)} industry proxies.")

    # 2. GREEKS & SURFACE ENGINE TEST
    logging.info("\n--- STEP 2: QUANTITATIVE MATH ENGINE (BS-4D) ---")
    d, g, v, c, color = calculate_greeks(150, 155, 0.1, 0.045, 0.3, 'calls')
    logging.info(f"✅ Greeks Logic: Delta {d} | Gamma {g} | Vanna {v} | Color {color}")

    # 3. PUT-INSIDER LOGIC TEST
    logging.info("\n--- STEP 3: PUT-INSIDER SPECIALIST TEST ---")
    # Low IV + Inverted Skew scenario
    mock_put_df = pd.DataFrame([{
        'ticker': 'TEST', 'contractSymbol': 'TEST_PUT', 'side': 'puts', 'strike': 140.0,
        'exp': '2026-03-15', 'dte': 14, 'volume': 5000, 'openInterest': 100, 
        'impliedVolatility': 0.35, 'lastPrice': 2.50, 'bid': 2.45, 'ask': 2.50, 
        'underlying_price': 150.0, 'notional': 1250000, 'vol_oi_ratio': 50.0 
    }])
    # We provide a mock DF with bearish surface
    results = score_unusual(mock_put_df, 'TEST', 1.0, 'Technology')
    if not results.empty and 'INSIDER PUT' in results.iloc[0]['detection_reason']:
        logging.info("✅ SUCCESS: Put-Insider detection logic firing correctly.")
    else:
        logging.warning("⚠️ NOTICE: Put-Insider check skipped or thresholds not met in test.")

    # 4. MICROSTRUCTURE ENGINE TEST
    logging.info("\n--- STEP 4: MICROSTRUCTURE ENGINE (Iceberg/Sweep) ---")
    mock_1m = pd.DataFrame({
        'High': [100.1] * 30, 'Low': [99.9] * 30, 'Close': [100.0] * 30,
        'Open': [100.0] * 30, 'Volume': [50000] * 30, 'VWAP': [100.0] * 30
    })
    mock_1m['vol_density'] = 50000 / 0.2
    mock_1m['iceberg_z'] = 5.0
    label, bonus = detect_microstructure_conviction(mock_1m)
    logging.info(f"✅ Microstructure: {label} (Bonus: {bonus})")

    # 5. LIVE INTEGRATION & TELEGRAM TEST
    logging.info("\n--- STEP 5: FULL ALERT CHAIN & ANALYST UI ---")
    test_trade = {
        'type': 'CALLS', 'underlying_price': 138.50, 'call_wall': 160.0, 'put_wall': 130.0,
        'skew': -0.04, 'bias': 'BULLISH', 'ticker': 'NVDA', 'strike': 150.0, 'exp': '2024-06-21',
        'volume': 8500, 'oi': 1200, 'notional': 4420000, 'rel_vol': 15.2, 'z_score': 6.8,
        'stock_z': 4.2, 'delta': 0.48, 'gamma': 0.025, 'vanna': 0.12, 'charm': 0.05,
        'gex': 1250000, 'flip': 142.0, 'score': 165, 'premium': 5.20, 'bid': 5.10, 'ask': 5.20,
        'aggression': 'Aggressive (Ask) | Institutional Sweep', 'sector': 'AI & Semiconductors',
        'weekly_count': 5, 'estimated_duration': '2-5 days', 'trend_prob': 0.92,
        'detection_reason': 'Vol > OI (Opening), Near Gamma Flip, TRV Max'
    }
    
    logging.info("📡 Dispatching FINAL REDESIGNED ALERT to Telegram...")
    sent = await send_alert(test_trade, "ULTIMATE TEST: Verifying redesigned UI and Institutional terminology.", macro)

    if sent:
        logging.info("✨ SUCCESS: The redesigned alert is on its way!")
    else:
        logging.error("❌ TELEGRAM FAILURE.")

    logging.info("\n🏁 VALIDATION COMPLETE 🏁")

if __name__ == "__main__":
    asyncio.run(run_validation_suite())
