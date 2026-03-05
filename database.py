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
                peak_pnl REAL DEFAULT 0.0
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
                bid_ask TEXT
            )
        ''')
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
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM long_term_flow')
        conn.commit()

def log_long_term_flow(ticker, direction, strike, expiry, premium, vol_oi, otm, bid_ask):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO long_term_flow (ticker, entry_time, direction, strike, expiry, premium, vol_oi, otm, bid_ask)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, datetime.now().isoformat(), direction, strike, expiry, premium, vol_oi, otm, bid_ask))
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

def log_trade(ticker, direction, leverage, timeframe_hours, conviction, entry_price, target, stop, iv_rank=0):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (ticker, entry_time, direction, leverage, timeframe_hours, 
                              conviction_score, entry_price, target_price, stop_loss, iv_rank)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, datetime.now().isoformat(), direction.upper(), leverage, timeframe_hours, 
              conviction, entry_price, target, stop, iv_rank))
        conn.commit()

def get_performance_stats():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*), SUM(is_win) FROM trades WHERE status = "CLOSED"')
        total, wins = cursor.fetchone()
        
        cursor.execute('SELECT AVG(is_win) FROM trades WHERE conviction_score >= 8 AND status = "CLOSED"')
        high_conv_win_rate = cursor.fetchone()[0] or 0
        
        if not total or total == 0:
            return "No historical performance data available."
        
        win_rate = (wins / total) * 100
        stats = f"Overall Win Rate: {win_rate:.1f}% ({total} trades)\n"
        stats += f"High Conviction Win Rate: {high_conv_win_rate*100:.1f}%"
        return stats
