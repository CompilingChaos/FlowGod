import pandas as pd
import numpy as np
import logging
import math
from scipy.stats import norm
from historical_db import get_stats, get_ticker_baseline
from config import MIN_VOLUME, MIN_NOTIONAL, MIN_VOL_OI_RATIO, MIN_RELATIVE_VOL, MIN_STOCK_Z_SCORE

def get_stock_heat(ticker, live_vol):
    baseline = get_ticker_baseline(ticker)
    if baseline and baseline['std_dev'] > 0:
        z_score = (live_vol - baseline['avg_vol']) / baseline['std_dev']
        return z_score, baseline.get('sector', 'Unknown')
    return 0, "Unknown"

def calculate_greeks(S, K, T, r, sigma, option_type='calls'):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0: return 0, 0, 0, 0
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        if option_type == 'calls': delta = norm.cdf(d1)
        else: delta = norm.cdf(d1) - 1
        gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
        vanna = (norm.pdf(d1) * d2) / sigma
        charm = -norm.pdf(d1) * (r / (sigma * math.sqrt(T)) - d2 / (2 * T))
        return round(delta, 3), round(gamma, 4), round(vanna, 4), round(charm, 4)
    except: return 0, 0, 0, 0

def calculate_volatility_surface(df):
    """Maps IV Skew and Term Structure."""
    if df.empty: return 0, 0, "NEUTRAL"
    try:
        # Term Structure
        term = df.groupby('dte')['impliedVolatility'].mean().sort_index()
        contango = term.iloc[1] - term.iloc[0] if len(term) > 1 else 0
        
        # IV Skew (25 Delta approximation)
        puts = df[(df['side'] == 'puts') & (df['strike'] < df['underlying_price'])]
        calls = df[(df['side'] == 'calls') & (df['strike'] > df['underlying_price'])]
        skew = puts['impliedVolatility'].mean() - calls['impliedVolatility'].mean()
        
        bias = "BULLISH" if skew < -0.05 else "BEARISH" if skew > 0.10 else "NEUTRAL"
        return round(skew, 3), round(contango, 3), bias
    except: return 0, 0, "NEUTRAL"

def map_gex_walls(df):
    """Identifies the massive Call and Put walls across all expirations."""
    if df.empty: return 0, 0, 0
    try:
        df['net_gex'] = np.where(df['side'] == 'calls', 
                                 df['gamma'] * df['openInterest'] * 100 * df['underlying_price'],
                                 -df['gamma'] * df['openInterest'] * 100 * df['underlying_price'])
        strike_gex = df.groupby('strike')['net_gex'].sum()
        call_wall = strike_gex.idxmax()
        put_wall = strike_gex.idxmin()
        
        # Zero Gamma Flip
        strike_gex_sorted = strike_gex.sort_index()
        flip = 0
        for i in range(len(strike_gex_sorted)-1):
            if np.sign(strike_gex_sorted.iloc[i]) != np.sign(strike_gex_sorted.iloc[i+1]):
                flip = strike_gex_sorted.index[i]
                break
        return call_wall, put_wall, flip
    except: return 0, 0, 0

def score_unusual(df, ticker, stock_z, sector="Unknown", candle=None):
    if df.empty: return pd.DataFrame()
    
    # 1. Surface Mapping
    skew, contango, vol_bias = calculate_volatility_surface(df)
    
    # 2. Advanced Greeks & GEX
    # Pre-calculate Greeks for all rows to map walls
    for idx, row in df.iterrows():
        T = max(0.001, row['dte']) / 365.0
        d, g, v, c = calculate_greeks(row['underlying_price'], row['strike'], T, 0.045, row['impliedVolatility'], row['side'])
        df.at[idx, 'delta'], df.at[idx, 'gamma'], df.at[idx, 'vanna'], df.at[idx, 'charm'] = d, g, v, c
        df.at[idx, 'gex'] = g * row['openInterest'] * 100 * row['underlying_price']

    call_wall, put_wall, flip = map_gex_walls(df)
    spot = df.iloc[0]['underlying_price']
    
    # 3. Dark Pool Proxy
    dark_z = candle.get('dark_z_max', 0) if candle else 0
    trv_label = "Standard Flow"
    trv_bonus = 0
    if candle:
        buyer_agg = (candle['Close'] - candle['Low']) / (candle['High'] - candle['Low'] + 0.01)
        if buyer_agg > 0.8 and candle['Close'] > candle['vwap']:
            trv_label, trv_bonus = "Institutional Sweep (TRV Max)", 50
        elif dark_z > 4.0:
            trv_label, trv_bonus = "Dark Pool Absorption Detected", 60

    baseline = get_ticker_baseline(ticker)
    trust_mult = baseline.get('trust_score', 1.0) if baseline else 1.0
    results = []

    for _, row in df.iterrows():
        # Aggression
        agg_label, agg_bonus = "Neutral (Mid)", 10
        if row['lastPrice'] >= row['ask'] and row['ask'] > 0: agg_label, agg_bonus = "Aggressive (Ask)", 50
        elif row['lastPrice'] <= row['bid'] and row['bid'] > 0: agg_label, agg_bonus = "Passive (Bid)", 0
        
        score = 0
        if row['volume'] > 1000: score += 20
        if row['notional'] > 500000: score += 40
        score += agg_bonus + trv_bonus
        
        # ALPHA BONUSES
        if abs(spot - call_wall) / spot < 0.01: score -= 30 # Into resistance
        if (vol_bias == "BULLISH" and row['side'] == 'calls') or (vol_bias == "BEARISH" and row['side'] == 'puts'): score += 40
        if abs(row['delta']) > 0.45 and abs(row['delta']) < 0.55: score += 30
        
        score = int(score * trust_mult)
        if (row['volume'] > row['openInterest'] and row['volume'] > 500) or score >= 85:
            results.append({
                'ticker': ticker, 'contract': row['contractSymbol'], 'type': row['side'].upper(),
                'strike': row['strike'], 'exp': row['exp'], 'volume': int(row['volume']),
                'oi': int(row['openInterest']), 'premium': round(row['lastPrice'], 2),
                'notional': int(row['notional']), 'rel_vol': round(row['volume']/(get_stats(ticker, row['contractSymbol'])['avg_vol']+1), 1),
                'delta': row['delta'], 'gamma': row['gamma'], 'vanna': row['vanna'], 'charm': row['charm'],
                'gex': int(row['gex']), 'call_wall': call_wall, 'put_wall': put_wall, 'flip': flip,
                'skew': skew, 'bias': vol_bias, 'score': score, 'aggression': f"{agg_label} | {trv_label}",
                'sector': sector, 'bid': row['bid'], 'ask': row['ask'],
                'detection_reason': f"Conviction Score {score} | {vol_bias} Skew"
            })
    return pd.DataFrame(results)

def process_results(all_results, macro_context, sector_performance):
    if not all_results: return []
    df = pd.DataFrame(all_results)
    
    # --- MULTI-LEG REVERSE ENGINEERING ---
    linked_alerts = []
    for (ticker, exp), group in df.groupby(['ticker', 'exp']):
        if len(group) >= 2:
            # Check for Vertical Spread (Same side, similar vol, different strikes)
            for side in ['CALLS', 'PUTS']:
                legs = group[group['type'] == side].sort_values('strike')
                if len(legs) >= 2:
                    leg1, leg2 = legs.iloc[0], legs.iloc[1]
                    vol_diff = abs(leg1['volume'] - leg2['volume']) / max(leg1['volume'], 1)
                    if vol_diff < 0.2: # High volume correlation
                        strategy = "Bull Call Spread" if side == 'CALLS' else "Bear Put Spread"
                        best_leg = legs.loc[legs['score'].idxmax()].to_dict()
                        best_leg['type'] = f"🔗 {strategy.upper()}"
                        best_leg['strike'] = f"{leg1['strike']} / {leg2['strike']}"
                        best_leg['notional'] = legs['notional'].sum()
                        best_leg['score'] += 40
                        linked_alerts.append(best_leg)
                        df = df[~df['contract'].isin(legs['contractSymbol'])]
    
    # Handle remaining individual trades and clusters
    final_alerts = linked_alerts
    for ticker, t_group in df.groupby('ticker'):
        if len(t_group) >= 3:
            best = t_group.loc[t_group['score'].idxmax()].to_dict()
            best['type'] = "📦 TICKER CLUSTER 📦"
            best['notional'], best['volume'] = t_group['notional'].sum(), t_group['volume'].sum()
            best['score'] += 50
            final_alerts.append(best)
        else: final_alerts.extend(t_group.to_dict('records'))
    return final_alerts
