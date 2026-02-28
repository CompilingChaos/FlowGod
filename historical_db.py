import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from config import DB_FILE

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''CREATE TABLE IF NOT EXISTS hist_vol_oi 
                 (ticker TEXT, contract TEXT, date TEXT, volume INTEGER, oi INTEGER)''')
    conn.commit()
    return conn

def update_historical(ticker, chain_df):
    conn = init_db()
    today = datetime.now().date().isoformat()
    for _, row in chain_df.iterrows():
        contract = row['contractSymbol']
        vol = 0 if pd.isna(row.get('volume')) else int(row['volume'])
        oi = 0 if pd.isna(row.get('openInterest')) else int(row['openInterest'])
        conn.execute("INSERT OR REPLACE INTO hist_vol_oi VALUES (?,?,?,?,?)",
                     (ticker, contract, today, vol, oi))
    conn.commit()

def get_avg_vol_oi(ticker, contract, days=30):
    conn = init_db()
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    df = pd.read_sql_query(
        "SELECT AVG(volume) as avg_vol, AVG(oi) as avg_oi FROM hist_vol_oi "
        "WHERE ticker=? AND contract=? AND date >= ?", 
        conn, params=(ticker, contract, cutoff))
    return df.iloc[0] if not df.empty else pd.Series({'avg_vol': 0, 'avg_oi': 0})
