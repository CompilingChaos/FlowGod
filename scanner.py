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
    if df.empty: return 0, 0, "NEUTRAL"
    try:
        term = df.groupby('dte')['impliedVolatility'].mean().sort_index()
        contango = term.iloc[1] - term.iloc[0] if len(term) > 1 else 0
        puts = df[(df['side'] == 'puts') & (df['strike'] < df['underlying_price'])]
        calls = df[(df['side'] == 'calls') & (df['strike'] > df['underlying_price'])]
        skew = puts['impliedVolatility'].mean() - calls['impliedVolatility'].mean()
        bias = "BULLISH" if skew < -0.05 else "BEARISH" if skew > 0.10 else "NEUTRAL"
        return round(skew, 3), round(contango, 3), bias
    except: return 0, 0, "NEUTRAL"

def map_gex_walls(df):
    if df.empty: return 0, 0, 0
    try:
        df['net_gex'] = np.where(df['side'] == 'calls', 
                                 df['gamma'] * df['openInterest'] * 100 * df['underlying_price'],
                                 -df['gamma'] * df['openInterest'] * 100 * df['underlying_price'])
        strike_gex = df.groupby('strike')['net_gex'].sum()
        call_wall = strike_gex.idxmax()
        put_wall = strike_gex.idxmin()
        strike_gex_sorted = strike_gex.sort_index()
        flip = 0
        for i in range(len(strike_gex_sorted)-1):
            if np.sign(strike_gex_sorted.iloc[i]) != np.sign(strike_gex_sorted.iloc[i+1]):
                flip = strike_gex_sorted.index[i]
                break
        return call_wall, put_wall, flip
    except: return 0, 0, 0

def calculate_hvn_conviction(df_1m, t_type, spot):
    if df_1m is None or len(df_1m) < 20: return 1.0, "N/A"
    try:
        price_bins = np.round(df_1m['Close'] * 10) / 10
        hvn_price = df_1m.groupby(price_bins)['Volume'].sum().idxmax()
        conviction, label = 1.0, "POC Cleansed"
        if "CALL" in t_type:
            if spot < hvn_price: conviction, label = 0.3, f"Trap: Below HVN (${hvn_price})"
        else:
            if spot > hvn_price: conviction, label = 0.3, f"Trap: Above HVN (${hvn_price})"
        return conviction, label
    except: return 1.0, "N/A"

def detect_icebergs(df_1m):
    """Tier-3: Effort vs Result. Identifies massive limit orders absorbing volume."""
    if df_1m is None or len(df_1m) < 30: return False
    try:
        tr = (df_1m['High'] - df_1m['Low']).replace(0, 0.01)
        df_1m['vol_density'] = df_1m['Volume'] / tr
        roll_mean = df_1m['vol_density'].rolling(window=30).mean()
        roll_std = df_1m['vol_density'].rolling(window=30).std()
        df_1m['iceberg_z'] = (df_1m['vol_density'] - roll_mean) / (roll_std + 0.1)
        vol_90 = df_1m['Volume'].quantile(0.90)
        latest = df_1m.iloc[-5:] 
        return ((latest['iceberg_z'] > 3.0) & (latest['Volume'] > vol_90)).any()
    except: return False

def classify_aggression(last_price, bid, ask):
    if last_price >= ask and ask > 0: return "Aggressive (Ask)", 50
    if last_price <= bid and bid > 0: return "Passive (Bid)", 0
    return "Neutral (Mid)", 10

def score_unusual(df, ticker, stock_z, sector="Unknown", candle_df=None, social_vel=0.0):
    if df.empty: return pd.DataFrame()
    skew, contango, vol_bias = calculate_volatility_surface(df)
    baseline = get_ticker_baseline(ticker)
    trust_mult = baseline.get('trust_score', 1.0) if baseline else 1.0
    avg_social = baseline.get('avg_social_vel', 0.0) if baseline else 0.0
    hype_z = (social_vel / (avg_social + 0.1)) if avg_social > 0 else 0.0

    for idx, row in df.iterrows():
        T = max(0.001, row['dte']) / 365.0
        d, g, v, c = calculate_greeks(row['underlying_price'], row['strike'], T, 0.045, row['impliedVolatility'], row['side'])
        df.at[idx, 'delta'], df.at[idx, 'gamma'], df.at[idx, 'vanna'], df.at[idx, 'charm'] = d, g, v, c
        df.at[idx, 'gex'] = g * row['openInterest'] * 100 * row['underlying_price']
    call_wall, put_wall, flip = map_gex_walls(df)
    spot = df.iloc[0]['underlying_price']
    
    # Tier-3 Alpha Aggression
    trv_label, trv_bonus = "Standard Flow", 10
    if candle_df is not None:
        if detect_icebergs(candle_df): trv_label, trv_bonus = "Institutional ICEBERG", 65
        else:
            last_c = candle_df.iloc[-1]
            buyer_agg = (last_c['Close'] - last_c['Low']) / (last_c['High'] - last_c['Low'] + 0.01)
            vwap = candle_df['VWAP'].iloc[-1] if 'VWAP' in candle_df.columns else last_c['Close']
            if buyer_agg > 0.8 and last_c['Close'] > vwap: trv_label, trv_bonus = "Sweep (TRV Max)", 50

    results = []
    for _, row in df.iterrows():
        agg_label, agg_bonus = classify_aggression(row['lastPrice'], row['bid'], row['ask'])
        hvn_conv, hvn_label = calculate_hvn_conviction(candle_df, row['side'].upper(), spot)
        score = 0
        if row['volume'] > 1000: score += 20
        if row['notional'] > 500000: score += 40
        score += agg_bonus + trv_bonus
        if abs(spot - call_wall) / spot < 0.01: score -= 30
        if (vol_bias == "BULLISH" and row['side'] == 'calls') or (vol_bias == "BEARISH" and row['side'] == 'puts'): score += 40
        
        score = int(score * trust_mult * hvn_conv)
        if (row['volume'] > row['openInterest'] and row['volume'] > 500) or score >= 85:
            results.append({
                'ticker': ticker, 'contract': row['contractSymbol'], 'type': row['side'].upper(),
                'strike': row['strike'], 'exp': row['exp'], 'volume': int(row['volume']),
                'oi': int(row['openInterest']), 'premium': round(row['lastPrice'], 2),
                'notional': int(row['notional']), 'rel_vol': round(row['volume']/(get_stats(ticker, row['contractSymbol'])['avg_vol']+1), 1),
                'delta': row['delta'], 'gamma': row['gamma'], 'vanna': row['vanna'], 'charm': row['charm'],
                'gex': int(row['gex']), 'call_wall': call_wall, 'put_wall': put_wall, 'flip': flip,
                'skew': skew, 'bias': vol_bias, 'score': score, 'aggression': f"{agg_label} | {trv_label} | {hvn_label}",
                'sector': sector, 'bid': row['bid'], 'ask': row['ask'], 'underlying_price': spot,
                'hype_z': round(hype_z, 1),
                'detection_reason': f"Score {score} | {hvn_label} | {vol_bias}"
            })
    return pd.DataFrame(results)

def generate_system_verdict(trade):
    t_type, spot = trade['type'], trade.get('underlying_price', 0)
    call_wall, put_wall = trade.get('call_wall', 0), trade.get('put_wall', 0)
    skew, agg = trade.get('skew', 0), trade.get('aggression', "")
    verdict, logic = "NEUTRAL", "Insufficient conviction."
    if "CALL" in t_type and "Aggressive" in agg:
        if skew < 0: verdict, logic = "CALL (Long)", "Aggressive sweep + Bullish Skew."
        elif spot > 0 and put_wall > 0 and (spot - put_wall) / spot < 0.02: verdict, logic = "CALL (Long)", "Support bounce at Put Wall."
        else: verdict, logic = "BUY (Stock)", "Bullish flow, conservative tech."
    elif "PUT" in t_type and "Aggressive" in agg:
        if skew > 0.05: verdict, logic = "PUT (Short)", "Aggressive sweep + Bearish Skew."
        elif spot > 0 and call_wall > 0 and (call_wall - spot) / spot < 0.02: verdict, logic = "PUT (Short)", "Resistance rejection at Call Wall."
        else: verdict, logic = "PUT (Short)", "Bearish flow detected."
    elif "Dark Pool" in agg or "ICEBERG" in agg: verdict, logic = "BUY (Stock)", "Institutional absorption."
    return verdict, logic

def process_results(all_results, macro_context, sector_performance):
    if not all_results: return []
    df = pd.DataFrame(all_results)
    linked_alerts = []
    for (ticker, exp), group in df.groupby(['ticker', 'exp']):
        if len(group) >= 2:
            for side in ['CALLS', 'PUTS']:
                legs = group[group['type'] == side].sort_values('strike')
                if len(legs) >= 2:
                    leg1, leg2 = legs.iloc[0], legs.iloc[1]
                    if abs(leg1['volume'] - leg2['volume']) / max(leg1['volume'], 1) < 0.2:
                        best_leg = legs.loc[legs['score'].idxmax()].to_dict()
                        best_leg['type'] = f"🔗 {side[:-1]} SPREAD"
                        best_leg['strike'] = f"{leg1['strike']} / {leg2['strike']}"
                        best_leg['notional'] = legs['notional'].sum()
                        best_leg['score'] += 40
                        linked_alerts.append(best_leg)
                        df = df[~df['contract'].isin(legs['contractSymbol'])]
    final_alerts = linked_alerts
    for ticker, t_group in df.groupby('ticker'):
        if len(t_group) >= 3:
            best = t_group.loc[t_group['score'].idxmax()].to_dict()
            best['type'] = "📦 CLUSTER 📦"
            best['notional'], best['volume'] = t_group['notional'].sum(), t_group['volume'].sum()
            best['score'] += 50
            final_alerts.append(best)
        else: final_alerts.extend(t_group.to_dict('records'))
    return final_alerts
