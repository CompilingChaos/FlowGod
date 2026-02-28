import asyncio
import logging
import pandas as pd
from shadow_ingestion import ShadowDeepDive, run_deep_dive_analysis
from error_reporter import reporter
from data_fetcher import get_stock_info

# Configure logging for the test
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def run_validation_suite():
    logging.info("🚀 STARTING TIER-3 VALIDATION SUITE (Weekend Mode) 🚀")

    # 1. TEST SHADOW INGESTION (Stockgrid Handshake)
    logging.info("--- STEP 1: SHADOW HANDSHAKE TEST ---")
    shadow = ShadowDeepDive()
    whales = shadow.fetch_stockgrid_whales()
    
    if whales:
        logging.info(f"✅ SUCCESS: Shadow Layer ingested {len(whales)} whales from the last active session.")
        # Show a sample of the shadowed data
        sample = whales[0]
        logging.info(f"📊 SAMPLE DATA: {sample.get('ticker')} | Premium: ${sample.get('premium', 0):,} | Sweep: {sample.get('is_sweep')}")
    else:
        logging.warning("⚠️ NOTICE: Shadow endpoint returned empty. This is expected if the site clears weekend data, but the handshake did not CRASH.")

    # 2. TEST DEEP-DIVE SCANNER (Using a Liquid Ticker)
    logging.info("--- STEP 2: DEEP-DIVE SCANNER TEST (TSLA) ---")
    test_ticker = "TSLA"
    try:
        # We use the 'Deep Dive' route which bypasses heat thresholds
        results = run_deep_dive_analysis(test_ticker)
        
        if results is not None and not results.empty:
            logging.info(f"✅ SUCCESS: Deep-Dive analyzed {len(results)} high-conviction contracts for {test_ticker}.")
            logging.info(f"🎯 TOP SCORE: {results['score'].max()} on {results.iloc[0]['contract']}")
        else:
            logging.warning(f"⚠️ NOTICE: No unusual contracts found for {test_ticker} currently. Scanner is functional but quiet.")
    except Exception as e:
        logging.error(f"❌ DEEP-DIVE FAILED: {e}")

    # 3. TEST CRITICAL ERROR REPORTING (Simulated Failure)
    logging.info("--- STEP 3: ERROR REPORTING TEST (SIMULATED) ---")
    try:
        raise ValueError("SIMULATED_TEST_ERROR: Checking Tier-3 Reporting Layer.")
    except Exception as e:
        logging.info("📡 Dispatching simulated error to Telegram (Check your phone)...")
        await reporter.report_critical_error("VAL_SUITE_TEST", e, "Intentional test of the reporting layer.")

    logging.info("🏁 VALIDATION SUITE COMPLETE 🏁")

if __name__ == "__main__":
    asyncio.run(run_validation_suite())
