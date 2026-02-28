import pandas as pd
from historical_db import get_stats
from config import MIN_VOLUME, MIN_NOTIONAL, MIN_VOL_OI_RATIO, MIN_RELATIVE_VOL

def score_unusual(df, ticker):
    results = []
    for _, row in df.iterrows():
        contract = row['contractSymbol']
        stats = get_stats(ticker, contract)
        
        avg_vol = stats['avg_vol']
        std_dev = stats['std_dev']
        
        # 1. Calculate Relative Volume and Z-Score
        rel_vol = row['volume'] / (avg_vol + 1)
        z_score = (row['volume'] - avg_vol) / (std_dev + 1) if std_dev > 0 else 0
        
        # 2. Implied Volatility (IV) Analysis
        iv = row.get('impliedVolatility', 0)
        
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

        # 3. Hybrid Filtering Logic
        meets_mins = (
            row['volume'] >= MIN_VOLUME and 
            row['notional'] >= MIN_NOTIONAL and 
            row['vol_oi_ratio'] >= MIN_VOL_OI_RATIO and 
            rel_vol >= MIN_RELATIVE_VOL
        )
        
        # HIGH-SCORE BYPASS: Even if it misses one min threshold, 
        # if the score is very high (>= 85), we still flag it for AI review.
        is_whale = meets_mins or score >= 85

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
                'iv': round(iv, 2),
                'score': int(score),
                'bullish': row['side'] == 'calls'
            })
            
    return pd.DataFrame(results)
