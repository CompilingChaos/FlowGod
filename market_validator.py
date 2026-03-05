import sqlite3
import yfinance as yf
import time
from datetime import datetime, timedelta

DB_NAME = 'flow_god.db'

def validate_trades():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ticker, entry_price, direction, leverage, 
                   target_price, stop_loss, entry_time, timeframe_hours 
            FROM trades WHERE status = 'OPEN'
        """)
        open_trades = cursor.fetchall()

        for t in open_trades:
            tid, ticker, entry_price, direction, leverage, target, stop, entry_time_str, timeframe_hrs = t
            try:
                entry_time = datetime.fromisoformat(entry_time_str)
                now = datetime.now()
                
                # Fetch price data since entry
                ticker_obj = yf.Ticker(ticker)
                hist = ticker_obj.history(start=entry_time.strftime('%Y-%m-%d'), interval="1h")
                time.sleep(3)
                if hist.empty: continue

                # 1. Check for Intraday Stop Loss / Target / Liquidation
                # We iterate through the high/low of each hour since entry
                exit_reason = None
                exit_price = None
                
                for _, row in hist.iterrows():
                    high, low = row['High'], row['Low']
                    
                    # Liquidation Check (Standard -20% raw move for 5x, -10% for 10x)
                    liquidation_threshold = 1.0 / leverage
                    
                    if direction == 'LONG':
                        if low <= stop:
                            exit_reason, exit_price = "STOP LOSS", stop
                            break
                        if high >= target:
                            exit_reason, exit_price = "TARGET REACHED", target
                            break
                        if low <= entry_price * (1 - liquidation_threshold):
                            exit_reason, exit_price = "LIQUIDATED", entry_price * (1 - liquidation_threshold)
                            break
                    else: # SHORT
                        if high >= stop:
                            exit_reason, exit_price = "STOP LOSS", stop
                            break
                        if low <= target:
                            exit_reason, exit_price = "TARGET REACHED", target
                            break
                        if high >= entry_price * (1 + liquidation_threshold):
                            exit_reason, exit_price = "LIQUIDATED", entry_price * (1 + liquidation_threshold)
                            break

                # 2. Check for Timeframe Expiration
                if not exit_reason and now >= entry_time + timedelta(hours=timeframe_hrs):
                    exit_reason, exit_price = "TIMEFRAME EXPIRED", hist['Close'].iloc[-1]

                # 3. Finalize Trade if reason found
                if exit_reason:
                    pnl_raw = (exit_price - entry_price) / entry_price
                    if direction == 'SHORT': pnl_raw = -pnl_raw
                    pnl_leveraged = pnl_raw * leverage
                    is_win = 1 if pnl_leveraged > 0 else 0
                    
                    cursor.execute('''
                        UPDATE trades 
                        SET status = "CLOSED", pnl = ?, is_win = ?, 
                            exit_time = ?, exit_reason = ?
                        WHERE id = ?
                    ''', (pnl_leveraged, is_win, now.isoformat(), exit_reason, tid))
                    print(f"Closed {ticker}: {exit_reason} | PnL: {pnl_leveraged:.2%}")

            except Exception as e:
                print(f"Error validating {ticker}: {e}")
        conn.commit()

if __name__ == "__main__":
    validate_trades()
