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
        # This rewards tickers where whales consistently hold overnight
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

def process_results(all_results, macro_context):
    """Groups results into clusters and filters by Relative Sector Heat."""
    if not all_results: return []
    
    df = pd.DataFrame(all_results)
    spy_z = abs(macro_context.get('spy_pc', 0) / 0.5) 
    
    sector_heat = df.groupby('sector')['stock_z'].mean().to_dict()
    final_alerts = []
    
    for ticker, group in df.groupby('ticker'):
        if len(group) >= 3:
            best_trade = group.loc[group['score'].idxmax()].to_dict()
            ticker_sector = best_trade['sector']
            s_heat = sector_heat.get(ticker_sector, 0)
            
            is_valid_sector_move = s_heat > 2.0 and s_heat > (spy_z * 2)
            
            cluster_msg = f"CLUSTER: {len(group)} strikes targeted."
            if is_valid_sector_move:
                cluster_msg += f" 🔥 SECTOR STRENGTH: {ticker_sector} outperforming SPY."
            
            best_trade['aggression'] = cluster_msg
            best_trade['score'] += 50 
            best_trade['notional'] = group['notional'].sum()
            best_trade['volume'] = group['volume'].sum()
            final_alerts.append(best_trade)
        else:
            for _, trade in group.iterrows():
                t_dict = trade.to_dict()
                s_heat = sector_heat.get(t_dict['sector'], 0)
                if s_heat > 2.0 and spy_z > 1.5:
                    t_dict['score'] -= 20 
                final_alerts.append(t_dict)
                
    return final_alerts
