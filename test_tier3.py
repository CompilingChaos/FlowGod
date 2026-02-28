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
    logging.info("🚀 STARTING ULTIMATE TIER-3 VALIDATION SUITE 🚀")

    # 1. MACRO & ETF DATA TEST
    logging.info("\n--- STEP 1: MACRO & ETF DATA INTEGRITY ---")
    macro = get_advanced_macro()
    logging.info(f"✅ Macro Sentiment: {macro['sentiment']} (SPY: {macro['spy']}%)")
    
    sectors = get_sector_etf_performance()
    if sectors:
        logging.info(f"✅ Sector Data: Fetched {len(sectors)} industry proxies.")
    else:
        logging.error("❌ Sector Data: Failed to fetch ETF performance.")

    # 2. GREEKS & SURFACE ENGINE TEST (Math Validation)
    logging.info("\n--- STEP 2: QUANTITATIVE MATH ENGINE (Black-Scholes 4D) ---")
    # Test Data: S=150, K=155, T=0.1 (36 days), r=0.045, sigma=0.3
    d, g, v, c, color = calculate_greeks(150, 155, 0.1, 0.045, 0.3, 'calls')
    logging.info(f"✅ Greeks Logic: Delta {d} | Gamma {g} | Vanna {v} | Color {color}")
    
    if abs(d - 0.4) > 0.2: # Rough sanity check
        logging.error("❌ Greeks Math seems skewed.")

    # 3. MICROSTRUCTURE ENGINE TEST (Iceberg/Sweep Detection)
    logging.info("\n--- STEP 3: MICROSTRUCTURE ENGINE (Synthetic Order Book) ---")
    # Create mock 1m candle data for an Iceberg scenario
    mock_data = {
        'High': [100.1] * 30,
        'Low': [99.9] * 30,
        'Close': [100.0] * 30,
        'Open': [100.0] * 30,
        'Volume': [50000] * 30, # Extreme constant volume
        'VWAP': [100.0] * 30
    }
    mock_df = pd.DataFrame(mock_data)
    # Force an iceberg Z-score trigger
    mock_df['vol_density'] = 50000 / 0.2
    mock_df['iceberg_z'] = 5.0
    
    label, bonus = detect_microstructure_conviction(mock_df)
    logging.info(f"✅ Microstructure: {label} (Bonus: {bonus})")

    # 4. HYBRID SIGNAL ENGINE TEST (Verdicts)
    logging.info("\n--- STEP 4: HYBRID SIGNAL ENGINE (Decision Logic) ---")
    test_trade = {
        'type': 'CALLS',
        'underlying_price': 100.0,
        'call_wall': 110.0,
        'put_wall': 90.0,
        'skew': -0.06, # Bullish skew
        'aggression': 'Aggressive (Ask) | Institutional Sweep',
        'ticker': 'TEST',
        'strike': 105.0,
        'exp': '2026-03-15',
        'volume': 1000,
        'oi': 100,
        'notional': 500000,
        'rel_vol': 10.0,
        'z_score': 5.0,
        'stock_z': 3.0,
        'delta': 0.5,
        'gamma': 0.02,
        'vanna': 0.05,
        'charm': 0.01,
        'gex': 100000,
        'flip': 102.0,
        'score': 150,
        'premium': 2.50,
        'bid': 2.40,
        'ask': 2.50
    }
    verdict, logic = generate_system_verdict(test_trade)
    logging.info(f"✅ System Verdict: {verdict} | Logic: {logic}")

    # 5. LIVE INTEGRATION & TELEGRAM TEST
    logging.info("\n--- STEP 5: FULL ALERT CHAIN & AI ANALYST ---")
    logging.info("📡 Dispatching ULTIMATE VALIDATION ALERT to Telegram...")
    
    ticker_context = "VALIDATION MODE: Testing RAG memory and multi-vector analytical pipeline."
    
    # This will trigger Gemini 3 Flash Preview and send to Telegram
    sent = await send_alert(test_trade, ticker_context, macro)

    if sent:
        logging.info("✨ SUCCESS: The validation alert is on its way to your phone!")
    else:
        logging.error("❌ TELEGRAM FAILURE: Check your Bot Token and Chat ID.")

    logging.info("\n🏁 VALIDATION SUITE COMPLETE 🏁")

if __name__ == "__main__":
    asyncio.run(run_validation_suite())
