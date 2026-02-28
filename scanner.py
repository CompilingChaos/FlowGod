import pandas as pd
from historical_db import get_avg_vol_oi
from config import MIN_VOLUME, MIN_NOTIONAL, MIN_VOL_OI_RATIO, MIN_RELATIVE_VOL

def score_unusual(df, ticker):
    results = []
    for _, row in df.iterrows():
        contract = row['contractSymbol']
        avg = get_avg_vol_oi(ticker, contract)
        rel_vol = row['volume'] / (avg['avg_vol'] + 1)
        
        score = 0
        if row['volume'] > 1000: score += 30
        if row['notional'] > 100000: score += 40
        if row['vol_oi_ratio'] > 15: score += 30
        if rel_vol > 10: score += 50
        if row['dte'] < 45 and row['moneyness'] < 15: score += 20
        
        if (row['volume'] >= MIN_VOLUME and 
            row['notional'] >= MIN_NOTIONAL and 
            row['vol_oi_ratio'] >= MIN_VOL_OI_RATIO and 
            rel_vol >= MIN_RELATIVE_VOL):
            
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
                'score': score,
                'bullish': row['side'] == 'calls'
            })
    return pd.DataFrame(results)
