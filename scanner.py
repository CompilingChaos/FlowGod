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
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0, 0, 0, 0
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        if option_type == 'calls':
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
            
        gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
        
        # Vanna: Delta change per 1% change in IV
        vanna = (norm.pdf(d1) * d2) / sigma
        
        # Charm: Delta decay per day
        charm = -norm.pdf(d1) * (r / (sigma * math.sqrt(T)) - d2 / (2 * T))
        
        return round(delta, 3), round(gamma, 4), round(vanna, 4), round(charm, 4)
    except:
        return 0, 0, 0, 0

def find_gamma_flip(df):
    """Identifies the price level where Market Makers flip from Long to Short Gamma."""
    if df.empty: return 0
    try:
        # Group by strike and sum GEX
        # GEX = Gamma * OI * 100 * Spot
        strike_gex = df.groupby('strike')['gex'].sum().sort_index()
        # Find where GEX crosses from positive to negative
        # This is a simplification but highly effective
        for i in range(len(strike_gex)-1):
            if np.sign(strike_gex.iloc[i]) != np.sign(strike_gex.iloc[i+1]):
                return strike_gex.index[i]
        return 0
    except:
        return 0

def calculate_trv_aggression(candle, ticker):
    """TRV = (Volume * (Close - Low)) / (High - Low) - Proxies buy vs sell conviction."""
    if not candle: return "Unknown", 0
    
    try:
        high, low, close, open_p, vwap = candle['High'], candle['Low'], candle['Close'], candle['Open'], candle['vwap']
        range_total = high - low
        if range_total == 0: return "Neutral", 5
        
        buyer_agg = (close - low) / range_total
        price_velocity = (close - open_p) / open_p
        vwap_div = (close - vwap) / vwap
        
        if buyer_agg > 0.8 and vwap_div > 0.001 and price_velocity > 0.0015:
            return "Institutional Sweep (TRV Max)", 50
        if buyer_agg < 0.2 and vwap_div < -0.001 and price_velocity < -0.0015:
            return "Institutional Dump (TRV Min)", 5
        return "Standard Flow", 10
    except:
        return "Unknown", 0

def classify_aggression(last_price, bid, ask):
    if last_price >= ask and ask > 0:
        return "Aggressive (Ask)", 50
    if last_price <= bid and bid > 0:
        return "Passive (Bid)", 0
    return "Neutral (Mid)", 10

def score_unusual(df, ticker, stock_z, sector="Unknown", candle=None):
    results = []
    if df.empty: return pd.DataFrame()

    baseline = get_ticker_baseline(ticker)
    trust_multiplier = baseline.get('trust_score', 1.0) if baseline else 1.0
    
    # 1. TRV Lie Detector
    trv_label, trv_bonus = calculate_trv_aggression(candle, ticker)
    
    # 2. Gamma Flip Proximity
    # We calculate local GEX first to find the flip
    temp_gex_df = []
    for _, row in df.iterrows():
        T = max(0.001, row['dte']) / 365.0
        r = 0.045
        d, g, v, c = calculate_greeks(row['underlying_price'], row['strike'], T, r, row['impliedVolatility'], row['side'])
        gex = g * row['openInterest'] * 100 * row['underlying_price']
        temp_gex_df.append({'strike': row['strike'], 'gex': gex})
    
    flip_level = find_gamma_flip(pd.DataFrame(temp_gex_df))
    spot_price = df.iloc[0]['underlying_price']
    near_flip = abs(spot_price - flip_level) / spot_price < 0.01 if flip_level > 0 else False

    for _, row in df.iterrows():
        contract = row['contractSymbol']
        stats = get_stats(ticker, contract)
        avg_vol = stats['avg_vol']
        std_dev = stats['std_dev']
        
        # 1. Option Stats
        rel_vol = row['volume'] / (avg_vol + 1)
        z_score = (row['volume'] - avg_vol) / (std_dev + 1) if std_dev > 0 else 0
        
        # 2. Advanced Greeks
        T = max(0.001, row['dte']) / 365.0
        r = 0.045
        iv = row.get('impliedVolatility', 0)
        delta, gamma, vanna, charm = calculate_greeks(row['underlying_price'], row['strike'], T, r, iv, row['side'])
        gex = gamma * row['openInterest'] * 100 * row['underlying_price']
        
        # 3. Aggression
        spread_agg, spread_bonus = classify_aggression(row['lastPrice'], row['bid'], row['ask'])
        final_agg_label = f"{spread_agg} | {trv_label}"
        
        score = 0
        if row['volume'] > 1000: score += 20
        if row['notional'] > 500000: score += 40
        if rel_vol > 8: score += 30
        
        # ALPHA BONUSES
        score += spread_bonus + trv_bonus
        if near_flip: score += 50 # Volatility Trigger Bonus
        if abs(delta) > 0.45 and abs(delta) < 0.55: score += 30 # ATM Conviction
        if vanna > 0.1: score += 20 # High Vol Sensitivity
        
        # STOCK HEAT
        if stock_z > MIN_STOCK_Z_SCORE: score += 40

        score = int(score * trust_multiplier)

        # 4. Filtering
        is_opening = row['volume'] > row['openInterest'] and row['volume'] > 500
        if is_opening or score >= 85:
            results.append({
                'ticker': ticker, 'contract': row['contractSymbol'], 'type': row['side'].upper(),
                'strike': row['strike'], 'exp': row['exp'], 'volume': int(row['volume']),
                'oi': int(row['openInterest']), 'premium': round(row['lastPrice'], 2),
                'notional': int(row['notional']), 'rel_vol': round(rel_vol, 1),
                'z_score': round(z_score, 1), 'stock_z': round(stock_z, 1),
                'delta': delta, 'gamma': gamma, 'vanna': vanna, 'charm': charm,
                'gex': int(gex), 'flip': round(flip_level, 2), 'score': score,
                'aggression': final_agg_label, 'sector': sector, 'bid': row['bid'], 'ask': row['ask']
            })
            
    return pd.DataFrame(results)

def process_results(all_results, macro_context, sector_performance):
    if not all_results: return []
    df = pd.DataFrame(all_results)
    final_alerts = []
    
    spy_perf = macro_context.get('spy', 0)

    # 1. SECTOR SWEEP
    for sector, s_group in df.groupby('sector'):
        if sector == "Unknown": continue
        unique_tickers = s_group['ticker'].unique()
        total_notional = s_group['notional'].sum()
        etf_perf = sector_performance.get(sector, 0)
        
        if len(unique_tickers) >= 3 and total_notional > 2000000:
            is_divergent = (etf_perf - spy_perf) > 1.5 # Sector relative strength
            sector_alert = s_group.loc[s_group['score'].idxmax()].to_dict()
            sector_alert['type'] = "🚨 SECTOR SWEEP 🚨"
            sector_alert['aggression'] = f"INSTITUTIONAL RS: {sector} Lead vs SPY" if is_divergent else f"SECTOR FLOW: {sector}"
            sector_alert['notional'] = total_notional
            sector_alert['score'] += 100 
            final_alerts.append(sector_alert)
            df = df[~df['ticker'].isin(unique_tickers)]

    # 2. TICKER CLUSTERING
    for ticker, t_group in df.groupby('ticker'):
        if len(t_group) >= 3:
            best_trade = t_group.loc[t_group['score'].idxmax()].to_dict()
            best_trade['type'] = "📦 TICKER CLUSTER 📦"
            best_trade['notional'] = t_group['notional'].sum()
            best_trade['volume'] = t_group['volume'].sum()
            best_trade['score'] += 50
            final_alerts.append(best_trade)
        else:
            final_alerts.extend(t_group.to_dict('records'))
                
    return final_alerts
