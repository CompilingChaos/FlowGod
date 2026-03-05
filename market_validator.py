import sqlite3
import yfinance as yf
import time
from datetime import datetime, timedelta

DB_NAME = 'flow_god.db'

def validate_trades():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, ticker, entry_price, direction, leverage FROM trades WHERE status = 'OPEN'")
        open_trades = cursor.fetchall()

        for tid, ticker, entry_price, direction, leverage in open_trades:
            try:
                # Fetch recent price data (today)
                ticker_obj = yf.Ticker(ticker)
                hist = ticker_obj.history(period="1d")
                time.sleep(3) # Rate limit protection
                if hist.empty: continue
                
                current_price = hist['Close'].iloc[-1]
                pnl_raw = (current_price - entry_price) / entry_price
                if direction.upper() == 'SHORT':
                    pnl_raw = -pnl_raw
                
                # Apply leverage
                pnl_leveraged = pnl_raw * leverage
                is_win = 1 if pnl_leveraged > 0 else 0
                
                # Close the trade
                cursor.execute('''
                    UPDATE trades 
                    SET status = "CLOSED", pnl = ?, is_win = ?
                    WHERE id = ?
                ''', (pnl_leveraged, is_win, tid))
                print(f"Validated {ticker}: PnL={pnl_leveraged:.2%}, Win={is_win}")
            except Exception as e:
                print(f"Error validating {ticker}: {e}")
        conn.commit()

if __name__ == "__main__":
    validate_trades()
