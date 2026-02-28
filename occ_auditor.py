import requests
import pandas as pd
import logging
import io
from datetime import datetime, timedelta
from historical_db import init_db, mark_alert_confirmed, update_trust_score
from error_reporter import notify_error_sync

# OCC Data Endpoints
# Volume: https://marketdata.theocc.com/daily-volume-statistics?reportDate=YYYYMMDD&format=csv
# OI: https://marketdata.theocc.com/daily-open-interest?reportDate=MM/DD/YYYY&action=download&format=csv

def audit_clearinghouse():
    """
    Downloads nightly OCC batch files to verify yesterday's whale alerts.
    This provides 100% accurate clearinghouse data.
    """
    # 1. Determine "Yesterday" (The last trading day)
    today = datetime.now()
    if today.weekday() == 0: # Monday
        yesterday = today - timedelta(days=3)
    else:
        yesterday = today - timedelta(days=1)
    
    date_str_vol = yesterday.strftime('%Y%m%d')
    date_str_oi = yesterday.strftime('%m/%d/%Y')
    
    logging.info(f"🚀 Starting Nightly OCC Audit for {date_str_oi}...")

    # 2. Fetch Volume Statistics (The 'Truth' of yesterday's trades)
    vol_url = f"https://marketdata.theocc.com/daily-volume-statistics?reportDate={date_str_vol}&format=csv"
    
    try:
        response = requests.get(vol_url, timeout=30)
        if response.status_code != 200:
            msg = f"OCC Volume Download Failed (Status {response.status_code})"
            logging.error(msg)
            notify_error_sync("OCC_AUDITOR_DOWNLOAD", Exception("HTTP Error"), msg)
            return

        # Parse CSV (Skip header metadata if present)
        df_vol = pd.read_csv(io.StringIO(response.text), skiprows=5)
        
        # 3. Cross-Reference with our Database
        conn = init_db()
        unconfirmed = conn.execute("SELECT contract, ticker, alert_vol FROM alerts_sent WHERE confirmed = 0").fetchall()
        
        for contract, ticker, alert_vol in unconfirmed:
            ticker_vol = df_vol[df_vol['Symbol'] == ticker]['Total'].sum()
            
            if ticker_vol > 0:
                if ticker_vol < alert_vol * 0.8:
                    logging.warning(f"⚠️ OCC DISCREPANCY: {ticker} volume seen was {alert_vol}, but only {ticker_vol} cleared.")
                    update_trust_score(ticker, -0.1)
                    mark_alert_confirmed(contract, -2) # Marked as "Cleared Fail"
                else:
                    logging.info(f"✅ OCC VERIFIED: {ticker} volume confirmed by Clearinghouse.")
                    update_trust_score(ticker, 0.05)
        
        conn.close()
        logging.info("OCC Nightly Audit Complete.")

    except Exception as e:
        msg = f"OCC Audit System Failure: {e}"
        logging.error(msg)
        notify_error_sync("OCC_AUDITOR_SYSTEM", e, msg)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        audit_clearinghouse()
    except Exception as e:
        logging.error(f"FATAL: {e}")
        notify_error_sync("OCC_AUDITOR_FATAL", e, "Crash in execution block.")
