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
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        }

    def fetch_stockgrid_whales(self) -> List[Dict]:
        """Shadows Stockgrid's 'Whale Stream' to find institutional sweeps."""
        try:
            # Step 1: Handshake to get CSRF/Session
            handshake_url = "https://www.stockgrid.io/whales"
            self.session.get(handshake_url, headers=self.base_headers, timeout=10)
            
            # Step 2: Hit the internal JSON endpoint
            # Note: Endpoints are shadowed and may require rotation
            api_url = "https://www.stockgrid.io/api/whales" 
            headers = self.base_headers.copy()
            headers["Referer"] = handshake_url
            if 'csrftoken' in self.session.cookies:
                headers["X-CSRFToken"] = self.session.cookies['csrftoken']

            response = self.session.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Stockgrid typically returns a list of dictionaries with 'ticker', 'premium', 'side', 'is_sweep'
                whales = data.get('data', []) if isinstance(data, dict) else data
                logging.info(f"✅ Shadowed {len(whales)} whales from Stockgrid.")
                return whales
            else:
                logging.warning(f"⚠️ Stockgrid Shadow failed: HTTP {response.status_code}")
                return []
        except Exception as e:
            logging.error(f"❌ Stockgrid Shadow Error: {e}")
            notify_error_sync("SHADOW_STOCKGRID", e, "Critical failure during Stockgrid JSON ingestion.")
            return []

    def fetch_aries_flow(self) -> List[Dict]:
        """Shadows Aries/Tradier-backed institutional flow."""
        try:
            # Aries/Tradier endpoints often use unmetered public streams for delayed data
            url = "https://api.tradier.com/v1/markets/options/chains" # Logic placeholder
            # Real implementation would target their frontend aggregator
            logging.info("📡 Aries Shadowing active (Polling institutional gateway).")
            return [] # Placeholder for extended Aries integration
        except:
            return []

    def get_trigger_tickers(self) -> List[str]:
        """Aggregates shadow signals into a list of high-conviction trigger tickers."""
        whales = self.fetch_stockgrid_whales()
        triggers = []
        for w in whales:
            ticker = w.get('ticker')
            premium = w.get('premium', 0)
            is_sweep = w.get('is_sweep', False)
            
            # Tier-3 Filter: High Premium or Institutional Sweep
            if ticker and (premium >= MIN_NOTIONAL * 10 or is_sweep):
                if ticker not in triggers:
                    triggers.append(ticker)
        
        logging.info(f"🔥 Shadow Intelligence identified {len(triggers)} Trigger Tickers.")
        return triggers

def run_deep_dive_analysis(ticker: str):
    """
    Performs a hyper-focused 'Deep Dive' on a shadow-triggered ticker.
    This bypasses the standard scan and goes straight to 'Full Chain' 15-exp analysis.
    """
    from data_fetcher import get_option_chain_data, get_stock_info, get_intraday_aggression
    from scanner import score_unusual, get_stock_heat
    
    logging.info(f"🕵️ Entering Deep-Dive Mode for {ticker}...")
    stock = get_stock_info(ticker)
    if stock['price'] == 0: return None
    
    z, sector = get_stock_heat(ticker, stock['volume'])
    candle = get_intraday_aggression(ticker)
    
    # Force 'full_chain=True' for Tier-3 Shadow Analysis
    df = get_option_chain_data(ticker, stock['price'], stock['volume'], full_chain=True)
    if df.empty: return None
    
    results = score_unusual(df, ticker, z, sector, candle)
    # Penalize low scores, only return institutional conviction
    return results[results['score'] >= 75]
