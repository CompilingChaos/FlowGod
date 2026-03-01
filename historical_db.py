import sqlite3
import pandas as pd
import os
import math
import logging
import re
from datetime import datetime, timedelta
from config import DB_FILE
from error_reporter import notify_error_sync

HISTORICAL_CSV = "historical_data.csv"

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        # Options History
        conn.execute('''CREATE TABLE IF NOT EXISTS hist_vol_oi 
                     (ticker TEXT, contract TEXT, date TEXT, volume INTEGER, oi INTEGER)''')
        # Alert Tracking (Vector 5 + RAG Memory)
        conn.execute('''CREATE TABLE IF NOT EXISTS alerts_sent 
                     (contract TEXT PRIMARY KEY, timestamp TEXT, 
                      ticker TEXT, type TEXT,
                      alert_vol INTEGER, alert_oi INTEGER, 
                      underlying_price REAL, outcome_3d REAL,
                      confirmed INTEGER DEFAULT 0)''')
        # Stock Baselines
        conn.execute('''CREATE TABLE IF NOT EXISTS ticker_stats 
                     (ticker TEXT PRIMARY KEY, avg_vol REAL, std_dev REAL, sector TEXT, 
                      trust_score REAL DEFAULT 1.0, avg_social_vel REAL DEFAULT 0.0,
                      earnings_date TEXT, last_updated TEXT)''')
        
        # Schema Migrations (Add columns if they don't exist)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(ticker_stats)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'avg_social_vel' not in columns:
            conn.execute("ALTER TABLE ticker_stats ADD COLUMN avg_social_vel REAL DEFAULT 0.0")
        if 'earnings_date' not in columns:
            conn.execute("ALTER TABLE ticker_stats ADD COLUMN earnings_date TEXT")
            
        conn.commit()
        return conn
    except Exception as e:
        logging.error(f"DB Init Error: {e}")
        notify_error_sync("DB_INIT", e, "Critical failure initializing SQLite database.")
        return None

def update_ticker_baseline(ticker, avg_vol, std_dev, sector="Unknown", social_vel=0.0, earnings_date=None):
    conn = init_db()
    if not conn: return
    try:
        res = conn.execute("SELECT trust_score, avg_social_vel, earnings_date FROM ticker_stats WHERE ticker = ?", (ticker,)).fetchone()
        current_trust = res[0] if res else 1.0
        new_social = social_vel if social_vel > 0 else (res[1] if res else 0.0)
        final_earnings = earnings_date if earnings_date else (res[2] if res else None)
        conn.execute("""INSERT OR REPLACE INTO ticker_stats 
                     (ticker, avg_vol, std_dev, sector, trust_score, avg_social_vel, earnings_date, last_updated) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                     (ticker, avg_vol, std_dev, sector, current_trust, new_social, final_earnings, datetime.now().isoformat()))
        conn.commit()
    except Exception as e:
        logging.error(f"Update baseline failed for {ticker}: {e}")
        notify_error_sync("DB_UPDATE_BASELINE", e, f"Failed to update baseline for {ticker}")
    finally:
        conn.close()

def get_ticker_baseline(ticker):
    conn = init_db()
    if not conn: return None
    try:
        res = conn.execute("SELECT avg_vol, std_dev, sector, trust_score, avg_social_vel, earnings_date FROM ticker_stats WHERE ticker = ?", (ticker,)).fetchone()
        if res:
            return {'avg_vol': res[0], 'std_dev': res[1], 'sector': res[2], 'trust_score': res[3], 'avg_social_vel': res[4], 'earnings_date': res[5]}
        return None
    except Exception as e:
        logging.error(f"Get baseline failed for {ticker}: {e}")
        return None
    finally:
        conn.close()

def update_trust_score(ticker, change):
    conn = init_db()
    if not conn: return
    try:
        conn.execute("UPDATE ticker_stats SET trust_score = trust_score + ? WHERE ticker = ?", (change, ticker))
        conn.execute("UPDATE ticker_stats SET trust_score = 2.0 WHERE trust_score > 2.0")
        conn.execute("UPDATE ticker_stats SET trust_score = 0.5 WHERE trust_score < 0.5")
        conn.commit()
    except Exception as e:
        logging.error(f"Trust score update failed: {e}")
    finally:
        conn.close()

def mark_alert_sent(contract, ticker="", trade_type="", vol=0, oi=0, price=0):
    conn = init_db()
    if not conn: return
    try:
        conn.execute("""INSERT OR REPLACE INTO alerts_sent 
                     (contract, timestamp, ticker, type, alert_vol, alert_oi, underlying_price, confirmed) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                     (contract, datetime.now().isoformat(), ticker, trade_type, vol, oi, price))
        conn.commit()
    except Exception as e:
        logging.error(f"Mark alert sent failed: {e}")
        notify_error_sync("DB_MARK_ALERT", e, f"Failed to log sent alert for {contract}")
    finally:
        conn.close()

def get_rag_context(ticker, trade_type):
    conn = init_db()
    if not conn: return "No historical precedent."
    try:
        query = """
            SELECT underlying_price, outcome_3d 
            FROM alerts_sent 
            WHERE ticker = ? AND type = ? AND outcome_3d IS NOT NULL
            ORDER BY timestamp DESC LIMIT 10
        """
        df = pd.read_sql_query(query, conn, params=(ticker, trade_type))
        conn.close()
        if df.empty: return "First time seeing high-conviction flow for this ticker/type."
        win_rate = (df['outcome_3d'] > 0).mean() if trade_type == 'CALLS' else (df['outcome_3d'] < 0).mean()
        avg_move = df['outcome_3d'].mean() * 100
        return f"RAG PRECEDENT: Last 10 similar {trade_type} on {ticker} had a {win_rate:.0%} win rate. Avg 3-day move: {avg_move:.1f}%."
    except Exception as e: 
        logging.error(f"RAG fetch failed: {e}")
        return "Memory system unavailable."

def get_weekly_campaign_stats(ticker, trade_type):
    """Counts how many times this ticker/type was alerted in the last 7 days."""
    conn = init_db()
    if not conn: return 0
    try:
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        res = conn.execute("SELECT COUNT(*) FROM alerts_sent WHERE ticker = ? AND type = ? AND timestamp > ?", (ticker, trade_type, cutoff)).fetchone()
        conn.close()
        return res[0] if res else 0
    except: return 0

def get_unconfirmed_alerts():
    conn = init_db()
    if not conn: return []
    try:
        cutoff = (datetime.now() - timedelta(hours=48)).isoformat()
        res = conn.execute("SELECT contract, alert_vol, alert_oi FROM alerts_sent WHERE confirmed = 0 AND timestamp > ?", (cutoff,)).fetchall()
        return res
    except Exception as e:
        logging.error(f"Unconfirmed alerts fetch failed: {e}")
        return []
    finally:
        conn.close()

def mark_alert_confirmed(contract, status=1):
    conn = init_db()
    if not conn: return
    try:
        conn.execute("UPDATE alerts_sent SET confirmed = ? WHERE contract = ?", (status, contract))
        conn.commit()
    except Exception as e:
        logging.error(f"Mark alert confirmed failed: {e}")
    finally:
        conn.close()

def needs_baseline_update(ticker):
    conn = init_db()
    if not conn: return True
    try:
        res = conn.execute("SELECT last_updated FROM ticker_stats WHERE ticker = ?", (ticker,)).fetchone()
        if not res: return True
        last_updated = datetime.fromisoformat(res[0]).date()
        return last_updated < datetime.now().date()
    except: return True
    finally:
        conn.close()

def load_from_csv():
    if os.path.exists(HISTORICAL_CSV):
        try:
            df = pd.read_csv(HISTORICAL_CSV)
            conn = init_db()
            if conn:
                df.to_sql('hist_vol_oi', conn, if_exists='replace', index=False)
                conn.close()
        except Exception as e:
            logging.error(f"Error loading CSV: {e}")
            notify_error_sync("DB_LOAD_CSV", e, "Failed to load historical data from CSV.")

def save_to_csv():
    conn = init_db()
    if not conn: return
    try:
        cutoff = (datetime.now() - timedelta(days=60)).date().isoformat()
        df = pd.read_sql_query("SELECT * FROM hist_vol_oi WHERE date >= ?", conn, params=(cutoff,))
        df.to_csv(HISTORICAL_CSV, index=False)
        conn.close()
    except Exception as e:
        logging.error(f"Error saving CSV: {e}")
        notify_error_sync("DB_SAVE_CSV", e, "Failed to persist database to CSV.")

def get_ticker_context(ticker, days=2):
    conn = init_db()
    if not conn: return "No historical context."
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    query = """
        SELECT date, SUM(volume) as total_vol, SUM(oi) as total_oi 
        FROM hist_vol_oi WHERE ticker = ? AND date >= ?
        GROUP BY date ORDER BY date DESC
    """
    try:
        df = pd.read_sql_query(query, conn, params=(ticker, cutoff))
        conn.close()
        if df.empty: return "First time seeing this ticker in 48 hours."
        context_str = "Last 48h Context:\n"
        for _, row in df.iterrows():
            context_str += f"- {row['date']}: Vol {row['total_vol']:,}, OI {row['total_oi']:,}\n"
        return context_str
    except Exception as e: return "Context unavailable."

def update_historical(ticker, chain_df):
    conn = init_db()
    if not conn: return
    try:
        today = datetime.now().date().isoformat()
        for _, row in chain_df.iterrows():
            contract = row['contractSymbol']
            vol = 0 if pd.isna(row.get('volume')) else int(row['volume'])
            oi = 0 if pd.isna(row.get('openInterest')) else int(row['openInterest'])
            conn.execute("INSERT OR REPLACE INTO hist_vol_oi VALUES (?,?,?,?,?)",
                         (ticker, contract, today, vol, oi))
        conn.commit()
    except Exception as e:
        logging.error(f"Historical update failed: {e}")
    finally:
        conn.close()

def get_stats(ticker, contract, days=30):
    conn = init_db()
    if not conn: return {'avg_vol': 0, 'avg_oi': 0, 'std_dev': 0}
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    query = """
        SELECT AVG(volume) as avg_vol, AVG(oi) as avg_oi,
               AVG(volume * volume) - (AVG(volume) * AVG(volume)) as variance
        FROM hist_vol_oi WHERE ticker=? AND contract=? AND date >= ?
    """
    try:
        df = pd.read_sql_query(query, conn, params=(ticker, contract, cutoff))
        conn.close()
        if df.empty or df.iloc[0]['avg_vol'] is None:
            return {'avg_vol': 0, 'avg_oi': 0, 'std_dev': 0}
        row = df.iloc[0]
        std_dev = math.sqrt(max(0, row['variance']))
        return {'avg_vol': row['avg_vol'], 'avg_oi': row['avg_oi'], 'std_dev': std_dev}
    except Exception as e: return {'avg_vol': 0, 'avg_oi': 0, 'std_dev': 0}

def is_alert_sent(contract):
    conn = init_db()
    if not conn: return False
    try:
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        conn.execute("DELETE FROM alerts_sent WHERE timestamp < ?", (cutoff,))
        conn.commit()
        res = conn.execute("SELECT 1 FROM alerts_sent WHERE contract = ?", (contract,)).fetchone()
        return res is not None
    except: return False
    finally:
        conn.close()
