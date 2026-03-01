import requests
import pandas as pd
import logging
import os
from datetime import datetime
from config import TELEGRAM_TOKEN
from error_reporter import notify_error_sync
from historical_db import save_trade_pattern

TRADES_FILE = "trades_to_verify.csv"

def harvest_saved_trades():
    """
    Pulls pending 'Save' clicks from Telegram and logs them.
    No persistent listener required.
    """
    if not TELEGRAM_TOKEN:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    
    try:
        response = requests.get(url)
        data = response.json()

        if not data.get("ok"):
            msg = f"Telegram Harvest Error: {data.get('description')}"
            logging.error(msg)
            notify_error_sync("BOT_LISTENER_API", Exception("API Error"), msg)
            return

        updates = data.get("result", [])
        if not updates:
            return

        # Load existing log
        if os.path.exists(TRADES_FILE):
            df = pd.read_csv(TRADES_FILE)
        else:
            df = pd.DataFrame(columns=["ticker", "type", "strike", "entry_price", "date", "p_l", "status"])

        new_saves = 0
        for update in updates:
            if "callback_query" in update:
                cb = update["callback_query"]
                cb_data = cb.get("data", "")
                
                if cb_data.startswith("save|"):
                    # Format: save|TICKER|TYPE|STRIKE|PRICE|GEX|VANNA|CHARM|SKEW
                    parts = cb_data.split("|")
                    ticker = parts[1]
                    t_type = parts[2]
                    strike = float(parts[3])
                    price = float(parts[4])
                    
                    gex, vanna, charm, skew = 0.0, 0.0, 0.0, 0.0
                    if len(parts) > 5:
                        gex = float(parts[5])
                        vanna = float(parts[6])
                        charm = float(parts[7])
                        skew = float(parts[8])

                    # Check if already logged (avoid duplicates)
                    is_duplicate = ((df['ticker'] == ticker) & 
                                   (df['type'] == t_type) & 
                                   (df['strike'] == strike) &
                                   (df['status'] == "OPEN")).any()
                    
                    if not is_duplicate:
                        new_row = {
                            "ticker": ticker,
                            "type": t_type,
                            "strike": strike,
                            "entry_price": price,
                            "date": datetime.now().isoformat(),
                            "p_l": 0.0,
                            "status": "OPEN"
                        }
                        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                        # Link to the recursive pattern database
                        save_trade_pattern(ticker, t_type, gex, vanna, charm, skew)
                        new_saves += 1
                        logging.info(f"✅ Harvested Save: {ticker} {t_type} {strike} (Math Snapshot Captured)")

        if new_saves > 0:
            df.to_csv(TRADES_FILE, index=False)
            logging.info(f"Successfully harvested {new_saves} new trades.")

    except Exception as e:
        msg = f"Harvesting failed: {e}"
        logging.error(msg)
        notify_error_sync("BOT_LISTENER_SYSTEM", e, msg)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    harvest_saved_trades()
