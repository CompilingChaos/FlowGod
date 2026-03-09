import sqlite3
from datetime import datetime

DB_NAME = 'flow_god.db'

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                entry_time TIMESTAMP,
                direction TEXT,
                leverage INTEGER,
                timeframe_hours INTEGER,
                conviction_score INTEGER,
                entry_price REAL,
                target_price REAL,
                stop_loss REAL,
                exit_time TIMESTAMP,
                status TEXT DEFAULT 'OPEN',
                pnl REAL DEFAULT 0.0,
                is_win INTEGER DEFAULT 0,
                exit_reason TEXT,
                iv_rank REAL,
                peak_pnl REAL DEFAULT 0.0,
                premium REAL DEFAULT 0.0,
                option_entry_price REAL DEFAULT 0.0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS long_term_flow (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                entry_time TIMESTAMP,
                direction TEXT,
                strike REAL,
                expiry TEXT,
                premium REAL,
                vol_oi REAL,
                otm REAL,
                bid_ask TEXT,
                side TEXT DEFAULT 'Unknown'
            )
        ''')
        
        cursor.execute("PRAGMA table_info(trades)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'option_entry_price' not in columns:
            cursor.execute("ALTER TABLE trades ADD COLUMN option_entry_price REAL DEFAULT 0.0")
            
        cursor.execute("PRAGMA table_info(long_term_flow)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'side' not in columns:
            cursor.execute("ALTER TABLE long_term_flow ADD COLUMN side TEXT DEFAULT 'Unknown'")
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date DATE UNIQUE,
                content TEXT
            )
        ''')
        conn.commit()

def log_report(content):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('INSERT OR REPLACE INTO daily_reports (report_date, content) VALUES (?, ?)', (today, content))
        conn.commit()

def get_last_week_reports():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT content FROM daily_reports ORDER BY report_date DESC LIMIT 7')
        return [row[0] for row in cursor.fetchall()]

def clear_daily_flow():
    """Clear today's helping values for a fresh start tomorrow."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM long_term_flow')
        conn.commit()

def log_long_term_flow(ticker, direction, strike, expiry, premium, vol_oi, otm, side):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO long_term_flow (ticker, entry_time, direction, strike, expiry, premium, vol_oi, otm, side)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, datetime.now().isoformat(), direction, strike, expiry, premium, vol_oi, otm, side))
        conn.commit()

def get_daily_trends():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT ticker, direction, SUM(premium) as total_prem, COUNT(*) as count 
            FROM long_term_flow 
            WHERE entry_time LIKE ?
            GROUP BY ticker, direction
            ORDER BY total_prem DESC
            LIMIT 10
        ''', (f'{today}%',))
        return cursor.fetchall()

def get_daily_trades():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT ticker, direction, entry_price, target_price, stop_loss, conviction_score, premium 
            FROM trades 
            WHERE entry_time LIKE ?
            ORDER BY premium DESC
        ''', (f'{today}%',))
        return cursor.fetchall()

def log_trade(ticker, direction, leverage, timeframe_hours, conviction, entry_price, target, stop, iv_rank=0, premium=0, option_entry=0):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (ticker, entry_time, direction, leverage, timeframe_hours, 
                              conviction_score, entry_price, target_price, stop_loss, iv_rank, premium, option_entry_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, datetime.now().isoformat(), direction.upper(), leverage, timeframe_hours, 
              conviction, entry_price, target, stop, iv_rank, premium, option_entry))
        conn.commit()

def get_ticker_daily_stats(ticker):
    """Get cumulative count and premium for calls/puts today for a specific ticker."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        stats = {"CALL": {"count": 0, "prem": 0}, "PUT": {"count": 0, "prem": 0}}
        
        cursor.execute('''
            SELECT direction, COUNT(*), SUM(premium) 
            FROM trades WHERE ticker = ? AND entry_time LIKE ? 
            GROUP BY direction
        ''', (ticker, f'{today}%'))
        for direction, count, prem in cursor.fetchall():
            d = "CALL" if "CALL" in str(direction).upper() else "PUT"
            stats[d]["count"] += count
            stats[d]["prem"] += (prem or 0)

        cursor.execute('''
            SELECT direction, COUNT(*), SUM(premium) 
            FROM long_term_flow WHERE ticker = ? AND entry_time LIKE ? 
            GROUP BY direction
        ''', (ticker, f'{today}%'))
        for direction, count, prem in cursor.fetchall():
            d = "CALL" if "CALL" in str(direction).upper() else "PUT"
            stats[d]["count"] += count
            stats[d]["prem"] += (prem or 0)
            
        return stats

def get_daily_performance_stats():
    """Get statistics for trades that were closed today."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get all trades closed today
        cursor.execute('''
            SELECT ticker, direction, pnl, is_win, conviction_score, exit_reason
            FROM trades 
            WHERE status = 'CLOSED' AND exit_time LIKE ?
        ''', (f'{today}%',))
        closed_trades = cursor.fetchall()
        
        if not closed_trades:
            return None
            
        total = len(closed_trades)
        wins = sum(1 for t in closed_trades if t['is_win'])
        avg_pnl = sum(t['pnl'] for t in closed_trades) / total
        
        # Identify 10/10 convictions closed today
        perfect_convictions = [t for t in closed_trades if t['conviction_score'] >= 10]
        
        return {
            "total": total,
            "wins": wins,
            "win_rate": (wins / total) * 100,
            "avg_pnl": avg_pnl,
            "perfect_convictions": perfect_convictions,
            "trades": closed_trades
        }

def get_performance_stats():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*), SUM(is_win) FROM trades WHERE status = "CLOSED"')
        row = cursor.fetchone()
        total, wins = (row[0], row[1]) if row else (0, 0)
        
        cursor.execute('SELECT AVG(is_win) FROM trades WHERE conviction_score >= 8 AND status = "CLOSED"')
        res = cursor.fetchone()
        high_conv_win_rate = res[0] if res and res[0] else 0
        
        if not total or total == 0:
            return "No historical performance data available."
        
        win_rate = (wins / total) * 100
        stats = f"Overall Win Rate: {win_rate:.1f}% ({total} trades)\n"
        stats += f"High Conviction Win Rate: {high_conv_win_rate*100:.1f}%"
        return stats
