import pandas as pd
from historical_db import get_stats, get_ticker_baseline
from config import MIN_VOLUME, MIN_NOTIONAL, MIN_VOL_OI_RATIO, MIN_RELATIVE_VOL, MIN_STOCK_Z_SCORE

def get_stock_heat(ticker, live_vol):
    """Checks if the stock volume is unusual (Light Check)."""
    baseline = get_ticker_baseline(ticker)
    if baseline and baseline['std_dev'] > 0:
        z_score = (live_vol - baseline['avg_vol']) / baseline['std_dev']
        return z_score
    return 0

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

def score_unusual(df, ticker, stock_z):
    results = []
    if df.empty: return pd.DataFrame()

    for _, row in df.iterrows():
        contract = row['contractSymbol']
        stats = get_stats(ticker, contract)
        
        avg_vol = stats['avg_vol']
        std_dev = stats['std_dev']
        
        # 1. Calculate Relative Volume and Z-Score (Options)
        rel_vol = row['volume'] / (avg_vol + 1)
        z_score = (row['volume'] - avg_vol) / (std_dev + 1) if std_dev > 0 else 0
        
        # 2. Implied Volatility (IV) Analysis
        iv = row.get('impliedVolatility', 0)
        
        # 3. Spread Aggression Analysis
        agg_label, agg_bonus = classify_aggression(row['lastPrice'], row['bid'], row['ask'])
        
        score = 0
        if row['volume'] > 1000: score += 20
        if row['notional'] > 100000: score += 30
        if row['notional'] > 500000: score += 40
        if row['vol_oi_ratio'] > 10: score += 20
        if row['vol_oi_ratio'] > 20: score += 30
        if rel_vol > 8: score += 30
        if z_score > 3: score += 50
        if z_score > 5: score += 30
        if row['dte'] < 45 and row['moneyness'] < 12: score += 20
        if iv > 0.8: score += 20 
        
        # AGGRESSION BONUS
        score += agg_bonus
        
        # STOCK HEAT MULTIPLIER
        if stock_z > MIN_STOCK_Z_SCORE: score += 40
        if stock_z > 5: score += 60

        # 4. Hybrid Filtering Logic
        meets_mins = (
            row['volume'] >= MIN_VOLUME and 
            row['notional'] >= MIN_NOTIONAL and 
            row['vol_oi_ratio'] >= MIN_VOL_OI_RATIO and 
            rel_vol >= MIN_RELATIVE_VOL
        )
        
        # Opening Position Bypass: Vol > OI
        is_opening = row['volume'] > row['openInterest'] and row['volume'] > 500

        # 5. Final Flagging
        is_whale = meets_mins or score >= 85 or is_opening

        if is_whale:
            results.append({
                'ticker': ticker,
                'contract': row['contractSymbol'],
                'type': row['side'].upper(),
                'strike': row['strike'],
                'exp': row['exp'],
                'volume': int(row['volume']) if not pd.isna(row['volume']) else 0,
                'oi': int(row['openInterest']) if not pd.isna(row['openInterest']) else 0,
                'premium': round(row['lastPrice'], 2) if not pd.isna(row['lastPrice']) else 0,
                'notional': int(row['notional']) if not pd.isna(row['notional']) else 0,
                'vol_oi': round(row['vol_oi_ratio'], 1) if not pd.isna(row['vol_oi_ratio']) else 0,
                'rel_vol': round(rel_vol, 1) if not pd.isna(rel_vol) else 0,
                'z_score': round(z_score, 1),
                'stock_z': round(stock_z, 1),
                'iv': round(iv, 2),
                'score': int(score),
                'aggression': agg_label,
                'bid': row['bid'],
                'ask': row['ask'],
                'bullish': row['side'] == 'calls'
            })
            
    return pd.DataFrame(results)
