import pandas as pd
import numpy as np
import logging
from historical_db import get_stats, get_ticker_baseline
from config import MIN_VOLUME, MIN_NOTIONAL, MIN_VOL_OI_RATIO, MIN_RELATIVE_VOL, MIN_STOCK_Z_SCORE

def get_stock_heat(ticker, live_vol):
    """Checks if the stock volume is unusual (Light Check)."""
    baseline = get_ticker_baseline(ticker)
    if baseline and baseline['std_dev'] > 0:
        z_score = (live_vol - baseline['avg_vol']) / baseline['std_dev']
        return z_score, baseline.get('sector', 'Unknown')
    return 0, "Unknown"

def classify_aggression(last_price, bid, ask):
    """Determines if the trade hit the bid, ask, or mid-point."""
    if last_price >= ask and ask > 0:
        return "Aggressive (Sweep/Ask)", 50
    if last_price <= bid and bid > 0:
        return "Passive (Sell/Bid)", 0
    if bid > 0 and ask > 0:
        mid = (bid + ask) / 2
        if last_price > mid:
            return "Leaning Bullish (Above Mid)", 25
    return "Neutral (Mid-Point)", 10

def score_unusual(df, ticker, stock_z, sector="Unknown"):
    results = []
    if df.empty: return pd.DataFrame()

    baseline = get_ticker_baseline(ticker)
    trust_multiplier = baseline.get('trust_score', 1.0) if baseline else 1.0

    for _, row in df.iterrows():
        contract = row['contractSymbol']
        stats = get_stats(ticker, contract)
        
        avg_vol = stats['avg_vol']
        std_dev = stats['std_dev']
        
        # 1. Option Z-Score
        rel_vol = row['volume'] / (avg_vol + 1)
        z_score = (row['volume'] - avg_vol) / (std_dev + 1) if std_dev > 0 else 0
        
        # 2. IV & Aggression
        iv = row.get('impliedVolatility', 0)
        agg_label, agg_bonus = classify_aggression(row['lastPrice'], row['bid'], row['ask'])
        
        score = 0
        if row['volume'] > 1000: score += 20
        if row['notional'] > 100000: score += 30
        if row['notional'] > 500000: score += 40
        if row['vol_oi_ratio'] > 10: score += 20
        if rel_vol > 8: score += 30
        if z_score > 3: score += 50
        
        # AGGRESSION BONUS
        score += agg_bonus
        
        # STOCK HEAT MULTIPLIER
        if stock_z > MIN_STOCK_Z_SCORE: score += 40
        if stock_z > 5: score += 60

        # FINAL SCORING WITH TRUST MULTIPLIER
        score = int(score * trust_multiplier)

        # 3. Filtering
        meets_mins = (
            row['volume'] >= MIN_VOLUME and 
            row['notional'] >= MIN_NOTIONAL and 
            row['vol_oi_ratio'] >= MIN_VOL_OI_RATIO
        )
        is_opening = row['volume'] > row['openInterest'] and row['volume'] > 500
        is_whale = meets_mins or score >= 85 or is_opening

        if is_whale:
            results.append({
                'ticker': ticker,
                'contract': row['contractSymbol'],
                'type': row['side'].upper(),
                'strike': row['strike'],
                'exp': row['exp'],
                'volume': int(row['volume']),
                'oi': int(row['openInterest']),
                'premium': round(row['lastPrice'], 2),
                'notional': int(row['notional']),
                'vol_oi': round(row['vol_oi_ratio'], 1),
                'rel_vol': round(rel_vol, 1),
                'z_score': round(z_score, 1),
                'stock_z': round(stock_z, 1),
                'iv': round(iv, 2),
                'score': int(score),
                'aggression': agg_label,
                'sector': sector,
                'bid': row['bid'],
                'ask': row['ask']
            })
            
    return pd.DataFrame(results)

def process_results(all_results, macro_context, sector_performance):
    """Groups results into high-conviction Sector and Ticker clusters."""
    if not all_results: return []
    
    df = pd.DataFrame(all_results)
    final_alerts = []
    
    # --- 1. SECTOR SWEEP DETECTION (Vector 3) ---
    # Total notional and unique tickers hit per sector
    for sector, s_group in df.groupby('sector'):
        if sector == "Unknown": continue
        
        unique_tickers = s_group['ticker'].unique()
        total_notional = s_group['notional'].sum()
        
        # ETF Baseline check: Is the sector outperforming its ETF/SPY?
        etf_perf = sector_performance.get(sector, 0)
        spy_perf = macro_context.get('spy', 0)
        
        # ALPHA: 3+ tickers hit AND >$2M total premium AND (Sector Heat or Divergence)
        if len(unique_tickers) >= 3 and total_notional > 2000000:
            # Check for institutional divergence
            is_divergent = abs(etf_perf - spy_perf) > 1.0 # Moving 1% different than market
            
            sector_alert = s_group.loc[s_group['score'].idxmax()].to_dict()
            sector_alert['type'] = "🚨 SECTOR SWEEP 🚨"
            sector_alert['aggression'] = f"INSTITUTIONAL CAMPAIGN: {len(unique_tickers)} tickers hit in {sector}."
            sector_alert['notional'] = total_notional
            sector_alert['score'] += 100 # Maximum conviction
            
            if is_divergent:
                sector_alert['analysis'] = f"Massive sector-wide allocation detected in {sector} diverging from SPY."
            
            final_alerts.append(sector_alert)
            # Remove these tickers from individual processing to avoid noise
            df = df[~df['ticker'].isin(unique_tickers)]

    # --- 2. TICKER CLUSTERING (Vertical/Horizontal) ---
    for ticker, t_group in df.groupby('ticker'):
        # If 3+ strikes or expirations hit -> Cluster
        if len(t_group) >= 3:
            best_trade = t_group.loc[t_group['score'].idxmax()].to_dict()
            total_notional = t_group['notional'].sum()
            total_vol = t_group['volume'].sum()
            
            best_trade['type'] = "📦 TICKER CLUSTER 📦"
            best_trade['aggression'] = f"Whale scaling: {len(t_group)} strikes/expirations targeted."
            best_trade['notional'] = total_notional
            best_trade['volume'] = total_vol
            best_trade['score'] += 50
            final_alerts.append(best_trade)
        else:
            # Individual high-conviction trades
            final_alerts.extend(t_group.to_dict('records'))
                
    return final_alerts
