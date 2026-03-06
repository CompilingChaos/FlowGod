import sqlite3
import yfinance as yf
import asyncio
from datetime import datetime, timedelta
from telegram import Bot
import os
import re
from dotenv import load_dotenv

load_dotenv()
DB_NAME = 'flow_god.db'
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

async def validate_trades():
    """Update ROI for all OPEN trades and close them if timeframe has passed."""
    print("📈 Starting Market Validation...")
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Fetch all OPEN trades
        cursor.execute("SELECT * FROM trades WHERE status = 'OPEN'")
        open_trades = cursor.fetchall()
        
        for trade in open_trades:
            ticker = trade['ticker']
            try:
                # Helper for safe numeric conversion from DB
                def safe_float(val, default=0.0):
                    try:
                        if val is None: return default
                        if isinstance(val, (int, float)): return float(val)
                        # Remove non-numeric artifacts
                        clean = re.sub(r'[^\d\.]', '', str(val))
                        return float(clean) if clean else default
                    except: return default

                # Robustly cast values from DB
                entry_price = safe_float(trade['entry_price'])
                option_entry = safe_float(trade['option_entry_price'])
                leverage = safe_float(trade['leverage'], 5.0)
                direction = str(trade['direction']).upper()
                entry_time = datetime.fromisoformat(trade['entry_time'])
                timeframe_hours = safe_float(trade['timeframe_hours'], 24.0)
                
                tk = yf.Ticker(ticker)
                hist = tk.history(period="1d")
                if hist.empty:
                    print(f"⚠️ No price data for {ticker}")
                    continue
                    
                current_price = float(hist['Close'].iloc[-1])
                
                # Calculate P/L
                if "LONG" in direction or "CALL" in direction:
                    raw_pnl = (current_price - entry_price) / entry_price
                else:
                    raw_pnl = (entry_price - current_price) / entry_price
                
                actual_leverage = leverage if option_entry == 0 else (leverage * 1.5)
                leveraged_pnl = float(raw_pnl * actual_leverage * 100)
                
                existing_peak = float(trade['peak_pnl'] or 0.0)
                peak_pnl = max(existing_peak, leveraged_pnl)
                
                is_expired = (datetime.now() - entry_time) > timedelta(hours=timeframe_hours)
                
                if is_expired:
                    status = 'CLOSED'
                    is_win = 1 if leveraged_pnl > 0 else 0
                    exit_reason = "Timeframe Expired"
                    entry_info = f"OptEntry: ${option_entry}" if option_entry > 0 else f"StockEntry: ${entry_price}"
                    print(f"✅ Closing {ticker} ({entry_info}): {leveraged_pnl:.1f}% ROI")
                else:
                    status = 'OPEN'
                    is_win = 0
                    exit_reason = None

                cursor.execute('''
                    UPDATE trades 
                    SET pnl = ?, is_win = ?, status = ?, exit_time = ?, exit_reason = ?, peak_pnl = ?
                    WHERE id = ?
                ''', (leveraged_pnl, is_win, status, datetime.now().isoformat() if is_expired else None, 
                      exit_reason, peak_pnl, trade['id']))
                
            except Exception as e:
                print(f"⚠️ Failed to validate {ticker}: {e}")

        conn.commit()

async def send_performance_leaderboard():
    """Summarize recent performance and send to Telegram."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Last 7 days stats
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        cursor.execute('''
            SELECT ticker, pnl, is_win, direction 
            FROM trades 
            WHERE status = 'CLOSED' AND exit_time > ?
            ORDER BY pnl DESC
        ''', (seven_days_ago,))
        
        recent_trades = cursor.fetchall()
        if not recent_trades: return

        total = len(recent_trades)
        wins = sum(1 for t in recent_trades if t['is_win'])
        avg_roi = sum(t['pnl'] for t in recent_trades) / total
        
        msg = "🏆 <b>WEEKLY PERFORMANCE LEADERBOARD</b>\n"
        msg += f"<i>(Past 7 Days of Validated Signals)</i>\n"
        msg += "━━━━━━━━━━━━━━━━━\n"
        msg += f"✅ <b>Win Rate:</b> {(wins/total)*100:.1f}%\n"
        msg += f"📈 <b>Avg leveraged ROI:</b> {avg_roi:+.1f}%\n"
        msg += "━━━━━━━━━━━━━━━━━\n"
        msg += "<b>Top Alpha Signals:</b>\n"
        
        for t in recent_trades[:5]:
            emoji = "🚀" if t['pnl'] > 0 else "📉"
            msg += f"{emoji} <b>{t['ticker']}</b> ({t['direction']}): {t['pnl']:+.1f}%\n"

        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='HTML')

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(validate_trades())
    if datetime.now().hour >= 21:
        loop.run_until_complete(send_performance_leaderboard())
