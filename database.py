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
                timeframe TEXT,
                entry_price REAL,
                status TEXT DEFAULT 'OPEN',
                pnl REAL DEFAULT 0.0,
                is_win INTEGER DEFAULT 0
            )
        ''')
        conn.commit()

def log_trade(ticker, direction, leverage, timeframe, entry_price):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (ticker, entry_time, direction, leverage, timeframe, entry_price)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (ticker, datetime.now().isoformat(), direction, leverage, timeframe, entry_price))
        conn.commit()

def get_performance_stats():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*), SUM(is_win) FROM trades WHERE status = "CLOSED"')
        total, wins = cursor.fetchone()
        if not total or total == 0:
            return "No historical performance data available."
        win_rate = (wins / total) * 100
        return f"Historical Performance: {win_rate:.1f}% Win Rate over {total} trades."
