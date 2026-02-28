import requests
import pandas as pd
import logging
import os
from datetime import datetime
from config import TELEGRAM_TOKEN

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
            logging.error(f"Telegram Harvest Error: {data.get('description')}")
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
                    # Format: save|TICKER|TYPE|STRIKE|PRICE
                    _, ticker, t_type, strike, price = cb_data.split("|")
                    
                    # Check if already logged (avoid duplicates)
                    is_duplicate = ((df['ticker'] == ticker) & 
                                   (df['type'] == t_type) & 
                                   (df['strike'] == float(strike)) &
                                   (df['status'] == "OPEN")).any()
                    
                    if not is_duplicate:
                        new_row = {
                            "ticker": ticker,
                            "type": t_type,
                            "strike": float(strike),
                            "entry_price": float(price),
                            "date": datetime.now().isoformat(),
                            "p_l": 0.0,
                            "status": "OPEN"
                        }
                        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                        new_saves += 1
                        logging.info(f"✅ Harvested Save: {ticker} {t_type} {strike}")

        if new_saves > 0:
            df.to_csv(TRADES_FILE, index=False)
            logging.info(f"Successfully harvested {new_saves} new trades.")

    except Exception as e:
        logging.error(f"Harvesting failed: {e}")

if __name__ == "__main__":
    harvest_saved_trades()
