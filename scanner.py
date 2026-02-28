import pandas as pd
import numpy as np
import logging
import math
from scipy.stats import norm
from historical_db import get_stats, get_ticker_baseline
from config import MIN_VOLUME, MIN_NOTIONAL, MIN_VOL_OI_RATIO, MIN_RELATIVE_VOL, MIN_STOCK_Z_SCORE

def get_stock_heat(ticker, live_vol):
    """Checks if the stock volume is unusual (Light Check)."""
    baseline = get_ticker_baseline(ticker)
    if baseline and baseline['std_dev'] > 0:
        z_score = (live_vol - baseline['avg_vol']) / baseline['std_dev']
        return z_score, baseline.get('sector', 'Unknown')
    return 0, "Unknown"

def calculate_greeks(S, K, T, r, sigma, option_type='calls'):
    """
    Local Black-Scholes engine to derive Delta and Gamma.
    S: Spot Price, K: Strike, T: Years to Exp, r: Risk-free rate, sigma: IV
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0, 0
    
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        
        # Delta
        if option_type == 'calls':
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
            
        # Gamma
        gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
        
        return round(delta, 3), round(gamma, 4)
    except:
        return 0, 0

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
        
        # 2. Local Greeks (Black-Scholes)
        T = max(0.001, row['dte']) / 365.0
        r = 0.045 # Current Risk Free Rate approximation
        iv = row.get('impliedVolatility', 0)
        delta, gamma = calculate_greeks(row['underlying_price'], row['strike'], T, r, iv, row['side'])
        
        # GEX Approximation: Gamma * OI * 100 * Spot
        # Measures how much dealers must hedge per 1% move
        gex = gamma * row['openInterest'] * 100 * row['underlying_price']
        
        # 3. Aggression
        agg_label, agg_bonus = classify_aggression(row['lastPrice'], row['bid'], row['ask'])
        
        score = 0
        if row['volume'] > 1000: score += 20
        if row['notional'] > 500000: score += 40
        if row['vol_oi_ratio'] > 10: score += 20
        if rel_vol > 8: score += 30
        if z_score > 3: score += 50
        
        # GREEKS BONUS
        if abs(delta) > 0.4 and abs(delta) < 0.6: score += 20 # At-the-money conviction
        if gamma > 0.05: score += 30 # High Gamma / Potential Squeeze
        
        score += agg_bonus
        if stock_z > MIN_STOCK_Z_SCORE: score += 40

        # FINAL SCORING WITH TRUST MULTIPLIER
        score = int(score * trust_multiplier)

        # 4. Filtering
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
                'delta': delta,
                'gamma': gamma,
                'gex': int(gex),
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
    
    # 1. SECTOR SWEEP DETECTION
    for sector, s_group in df.groupby('sector'):
        if sector == "Unknown": continue
        unique_tickers = s_group['ticker'].unique()
        total_notional = s_group['notional'].sum()
        etf_perf = sector_performance.get(sector, 0)
        spy_perf = macro_context.get('spy', 0)
        
        if len(unique_tickers) >= 3 and total_notional > 2000000:
            is_divergent = abs(etf_perf - spy_perf) > 1.0 
            sector_alert = s_group.loc[s_group['score'].idxmax()].to_dict()
            sector_alert['type'] = "🚨 SECTOR SWEEP 🚨"
            sector_alert['aggression'] = f"INSTITUTIONAL CAMPAIGN: {len(unique_tickers)} tickers hit in {sector}."
            sector_alert['notional'] = total_notional
            sector_alert['score'] += 100 
            if is_divergent:
                sector_alert['analysis'] = f"Massive sector-wide allocation detected in {sector} diverging from SPY."
            final_alerts.append(sector_alert)
            df = df[~df['ticker'].isin(unique_tickers)]

    # 2. TICKER CLUSTERING
    for ticker, t_group in df.groupby('ticker'):
        if len(t_group) >= 3:
            best_trade = t_group.loc[t_group['score'].idxmax()].to_dict()
            total_notional = t_group['notional'].sum()
            total_vol = t_group['volume'].sum()
            total_gex = t_group['gex'].sum()
            
            best_trade['type'] = "📦 TICKER CLUSTER 📦"
            best_trade['aggression'] = f"Whale scaling: {len(t_group)} strikes/expirations targeted."
            best_trade['notional'] = total_notional
            best_trade['volume'] = total_vol
            best_trade['gex'] = int(total_gex)
            best_trade['score'] += 50
            final_alerts.append(best_trade)
        else:
            final_alerts.extend(t_group.to_dict('records'))
                
    return final_alerts
