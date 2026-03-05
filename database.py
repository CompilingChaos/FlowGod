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
                exit_reason TEXT
            )
        ''')
        conn.commit()

def log_trade(ticker, direction, leverage, timeframe_hours, conviction, entry_price, target, stop):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (ticker, entry_time, direction, leverage, timeframe_hours, 
                              conviction_score, entry_price, target_price, stop_loss)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, direction.upper(), leverage, timeframe_hours, conviction, 
              entry_price, target, stop))
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
