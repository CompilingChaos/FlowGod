import requests
import pandas as pd
import logging
import time
from typing import List, Dict
from config import MIN_NOTIONAL
from error_reporter import notify_error_sync

class ShadowDeepDive:
    """
    Tier-3 Shadow Intelligence Layer.
    Bypasses standard APIs by shadowing internal JSON endpoints of institutional dashboards.
    Now includes Congressional "Pelosi" Signal (Public Disclosures).
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        }

    def fetch_congressional_trades(self) -> List[Dict]:
        """
        Shadows Public Congressional Disclosures (House Stock Watcher).
        Politicians are legally 'insiders' with long lead times.
        """
        try:
            # Publicly available daily aggregate of House disclosures
            url = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                # We only care about recent purchases (last 14 days) by high-conviction committees
                recent_trades = []
                for t in data[:100]: # Top 100 recent
                    ticker = t.get('ticker')
                    if ticker and ticker != '--' and t.get('type') == 'purchase':
                        recent_trades.append({
                            'ticker': ticker,
                            'premium': 0, # Notional often a range, but the signal is the 'Buy'
                            'is_sweep': False,
                            'source': f"CONGRESSIONAL_DISCLOSURE ({t.get('representative', 'Unknown')})"
                        })
                logging.info(f"🏛️ Shadowed {len(recent_trades)} recent Congressional purchases.")
                return recent_trades
            return []
        except Exception as e:
            logging.warning(f"⚠️ Congressional Shadowing failed: {e}")
            return []

    def fetch_stockgrid_whales(self) -> List[Dict]:
        """Shadows Stockgrid's 'Whale Stream' to find institutional sweeps."""
        try:
            handshake_url = "https://www.stockgrid.io/whales"
            self.session.get(handshake_url, headers=self.base_headers, timeout=10)
            
            api_url = "https://www.stockgrid.io/api/whales" 
            headers = self.base_headers.copy()
            headers["Referer"] = handshake_url
            if 'csrftoken' in self.session.cookies:
                headers["X-CSRFToken"] = self.session.cookies['csrftoken']

            response = self.session.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                whales = data.get('data', []) if isinstance(data, dict) else data
                logging.info(f"✅ Shadowed {len(whales)} whales from Stockgrid.")
                return whales
            return []
        except Exception as e:
            notify_error_sync("SHADOW_STOCKGRID", e, "Critical failure during Stockgrid JSON ingestion.")
            return []

    def fetch_cboe_block_trades(self) -> List[Dict]:
        """Shadows Cboe's Institutional Trade Optimizer / Large Print endpoints."""
        try:
            api_url = "https://markets.cboe.com/json/indices/indices_block_trades" 
            headers = self.base_headers.copy()
            headers["Referer"] = "https://markets.cboe.com/us/options/market_statistics/block_trades/"
            
            response = self.session.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                blocks = []
                for b in data.get('data', []):
                    blocks.append({
                        'ticker': b.get('symbol'),
                        'premium': b.get('total_premium', 0),
                        'is_sweep': b.get('is_block', True),
                        'source': 'CBOE_GATEWAY'
                    })
                logging.info(f"📡 Cboe Shadowed {len(blocks)} block trades.")
                return blocks
            return []
        except Exception as e:
            logging.warning(f"⚠️ Cboe Shadowing failed: {e}")
            return []

    def get_trigger_tickers(self) -> List[str]:
        """Aggregates shadow signals into a list of high-conviction trigger tickers."""
        whales = self.fetch_stockgrid_whales()
        blocks = self.fetch_cboe_block_trades()
        politics = self.fetch_congressional_trades()
        
        triggers = []
        combined = whales + blocks + politics
        
        for w in combined:
            ticker = w.get('ticker')
            premium = w.get('premium', 0)
            is_sweep = w.get('is_sweep', False)
            source = w.get('source', "")
            
            # Congressional trades are automatic triggers regardless of premium
            if "CONGRESSIONAL" in source:
                if ticker not in triggers: triggers.append(ticker)
                continue

            if ticker and (premium >= MIN_NOTIONAL * 10 or is_sweep):
                if ticker not in triggers:
                    triggers.append(ticker)
        
        logging.info(f"🔥 Shadow Intelligence identified {len(triggers)} Trigger Tickers.")
        return triggers

def run_deep_dive_analysis(ticker: str):
    """Performs a hyper-focused 'Deep Dive' on a shadow-triggered ticker."""
    from data_fetcher import get_option_chain_data, get_stock_info, get_intraday_aggression
    from scanner import score_unusual, get_stock_heat
    
    logging.info(f"🕵️ Entering Deep-Dive Mode for {ticker}...")
    stock = get_stock_info(ticker)
    if stock['price'] == 0: return None
    
    z, sector, earnings_date = get_stock_heat(ticker, stock['volume'])
    candle = get_intraday_aggression(ticker)
    
    df = get_option_chain_data(ticker, stock['price'], stock['volume'], full_chain=True)
    if df.empty: return None
    
    results = score_unusual(df, ticker, z, sector, candle, earnings_date=earnings_date)
    return results[results['score'] >= 75]
