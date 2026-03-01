import pandas as pd
import yfinance as yf
import logging
import os
from telegram import Bot
import asyncio
from datetime import datetime, timedelta
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from error_reporter import notify_error_sync
from historical_db import update_pattern_outcome

TRADES_FILE = "trades_to_verify.csv"

async def run_backtest():
    if not os.path.exists(TRADES_FILE):
        logging.info("No trades to verify.")
        return

    try:
        df = pd.read_csv(TRADES_FILE)
        open_trades = df[df['status'] == 'OPEN']
        
        if open_trades.empty:
            logging.info("No open trades to track.")
            return

        logging.info(f"Tracking performance for {len(open_trades)} trades...")
        
        summary_msg = "📈 TRADE PERFORMANCE UPDATE 📉\n\n"
        final_reports = []
        updated = False

        for idx, row in open_trades.iterrows():
            try:
                ticker = row['ticker']
                entry_price = row['entry_price']
                t_type = row['type']
                entry_date = datetime.fromisoformat(row['date'])
                
                # Fetch current price
                stock = yf.Ticker(ticker)
                current_price = stock.fast_info.get('lastPrice', 0)
                
                if current_price > 0:
                    p_l = ((current_price - entry_price) / entry_price) * 100
                    if t_type == 'PUTS': p_l = -p_l 
                    
                    df.at[idx, 'p_l'] = round(p_l, 2)
                    
                    # Learning & Closing Logic
                    days_open = (datetime.now() - entry_date).days
                    if days_open >= 7 or abs(p_l) >= 20:
                        df.at[idx, 'status'] = 'CLOSED'
                        update_pattern_outcome(ticker, t_type, p_l)
                        
                        # Final Notification details
                        final_reports.append(
                            f"🏁 FINAL OUTCOME: {ticker} {t_type} 🏁\n"
                            f"Result: {p_l:+.2f}%\n"
                            f"Duration: {days_open} days\n"
                            f"Verdict: {'✅ MODEL REWARDED' if p_l > 15 else '❌ TRAP DETECTED' if p_l < -10 else '⚪ NOISE LEARNED'}"
                        )
                        logging.info(f"🎓 Model Taught: {ticker} {t_type} outcome was {p_l:.1f}%")

                    status_icon = "🟢" if p_l > 0 else "🔴"
                    summary_msg += f"{status_icon} {ticker}: {p_l:+.2f}% (Price: ${current_price:.2f} vs Entry: ${entry_price:.2f})\n"
                    updated = True
            except Exception as e:
                logging.error(f"Backtest failed for {row['ticker']}: {e}")

        if updated:
            df.to_csv(TRADES_FILE, index=False)
            bot = Bot(token=TELEGRAM_TOKEN)
            try:
                # 1. Send General Performance Update
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=summary_msg)
                
                # 2. Send Final Closing Reports if any
                for report in final_reports:
                    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=report)
                    
                logging.info("Performance summary sent to Telegram.")
            except Exception as e:
                msg = f"Failed to send backtest summary: {e}"
                logging.error(msg)
                notify_error_sync("BACKTESTER_TELEGRAM", e, msg)

    except Exception as e:
        msg = f"Backtest System Failure: {e}"
        logging.error(msg)
        notify_error_sync("BACKTESTER_SYSTEM", e, msg)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_backtest())
    except Exception as e:
        logging.error(f"FATAL: {e}")
        notify_error_sync("BACKTESTER_FATAL", e, "Crash in execution block.")
