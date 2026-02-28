import sqlite3
import pandas as pd
import os
import math
import logging
from datetime import datetime, timedelta
from config import DB_FILE

HISTORICAL_CSV = "historical_data.csv"

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('''CREATE TABLE IF NOT EXISTS hist_vol_oi 
                     (ticker TEXT, contract TEXT, date TEXT, volume INTEGER, oi INTEGER)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS alerts_sent 
                     (contract TEXT PRIMARY KEY, timestamp TEXT)''')
        conn.commit()
        return conn
    except Exception as e:
        logging.error(f"DB Init Error: {e}")
        return None

def load_from_csv():
    if os.path.exists(HISTORICAL_CSV):
        try:
            df = pd.read_csv(HISTORICAL_CSV)
            conn = init_db()
            if conn:
                df.to_sql('hist_vol_oi', conn, if_exists='replace', index=False)
        except Exception as e:
            logging.error(f"Error loading CSV: {e}")

def save_to_csv():
    conn = init_db()
    if not conn: return
    try:
        cutoff = (datetime.now() - timedelta(days=60)).date().isoformat()
        df = pd.read_sql_query("SELECT * FROM hist_vol_oi WHERE date >= ?", conn, params=(cutoff,))
        df.to_csv(HISTORICAL_CSV, index=False)
    except Exception as e:
        logging.error(f"Error saving CSV: {e}")

def get_ticker_context(ticker, days=2):
    """Summarizes the last X days of activity for a specific ticker."""
    conn = init_db()
    if not conn: return "No historical context available."
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    
    query = """
        SELECT date, SUM(volume) as total_vol, SUM(oi) as total_oi 
        FROM hist_vol_oi 
        WHERE ticker = ? AND date >= ?
        GROUP BY date ORDER BY date DESC
    """
    try:
        df = pd.read_sql_query(query, conn, params=(ticker, cutoff))
        if df.empty:
            return "First time seeing this ticker in 48 hours."
        
        context_str = "Last 48h Context:\n"
        for _, row in df.iterrows():
            context_str += f"- {row['date']}: Vol {row['total_vol']:,}, OI {row['total_oi']:,}\n"
        return context_str
    except Exception as e:
        logging.error(f"Context retrieval failed for {ticker}: {e}")
        return "Context unavailable due to error."

def update_historical(ticker, chain_df):
    conn = init_db()
    if not conn: return
    today = datetime.now().date().isoformat()
    for _, row in chain_df.iterrows():
        contract = row['contractSymbol']
        vol = 0 if pd.isna(row.get('volume')) else int(row['volume'])
        oi = 0 if pd.isna(row.get('openInterest')) else int(row['openInterest'])
        conn.execute("INSERT OR REPLACE INTO hist_vol_oi VALUES (?,?,?,?,?)",
                     (ticker, contract, today, vol, oi))
    conn.commit()

def get_stats(ticker, contract, days=30):
    conn = init_db()
    if not conn: return {'avg_vol': 0, 'avg_oi': 0, 'std_dev': 0}
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    query = """
        SELECT 
            AVG(volume) as avg_vol, 
            AVG(oi) as avg_oi,
            AVG(volume * volume) - (AVG(volume) * AVG(volume)) as variance
        FROM hist_vol_oi 
        WHERE ticker=? AND contract=? AND date >= ?
    """
    try:
        df = pd.read_sql_query(query, conn, params=(ticker, contract, cutoff))
        if df.empty or df.iloc[0]['avg_vol'] is None:
            return {'avg_vol': 0, 'avg_oi': 0, 'std_dev': 0}
        row = df.iloc[0]
        std_dev = math.sqrt(max(0, row['variance']))
        return {'avg_vol': row['avg_vol'], 'avg_oi': row['avg_oi'], 'std_dev': std_dev}
    except Exception as e:
        logging.error(f"Stats query failed for {ticker}: {e}")
        return {'avg_vol': 0, 'avg_oi': 0, 'std_dev': 0}

def is_alert_sent(contract):
    conn = init_db()
    if not conn: return False
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    conn.execute("DELETE FROM alerts_sent WHERE timestamp < ?", (cutoff,))
    conn.commit()
    res = conn.execute("SELECT 1 FROM alerts_sent WHERE contract = ?", (contract,)).fetchone()
    return res is not None

def mark_alert_sent(contract):
    conn = init_db()
    if not conn: return
    conn.execute("INSERT OR REPLACE INTO alerts_sent (contract, timestamp) VALUES (?, ?)",
                 (contract, datetime.now().isoformat()))
    conn.commit()
