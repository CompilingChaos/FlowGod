import pandas as pd
import numpy as np
import logging
import math
from scipy.stats import norm
from historical_db import get_stats, get_ticker_baseline, get_weekly_campaign_stats, update_trust_score, get_matching_patterns
from config import MIN_VOLUME, MIN_NOTIONAL, MIN_VOL_OI_RATIO, MIN_RELATIVE_VOL, MIN_STOCK_Z_SCORE
from datetime import datetime, timedelta
from error_reporter import notify_error_sync
from data_fetcher import get_sec_filings, get_sector_divergence

def get_stock_heat(ticker, live_vol):
    try:
        baseline = get_ticker_baseline(ticker)
        if baseline and baseline['std_dev'] > 0:
            z_score = (live_vol - baseline['avg_vol']) / baseline['std_dev']
            return z_score, baseline.get('sector', 'Unknown'), baseline.get('earnings_date')
        return 0, "Unknown", None
    except Exception as e:
        notify_error_sync("SCANNER_HEAT", e, f"Failed to calculate heat for {ticker}")
        return 0, "Unknown", None

def calculate_greeks_vec(S, K, T, r, sigma, option_type='calls'):
    """Vectorized Black-Scholes Greeks calculation using NumPy."""
    try:
        T = np.maximum(T, 0.0001) 
        sigma = np.maximum(sigma, 0.01) 
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type == 'calls':
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
            
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        vanna = (norm.pdf(d1) * d2) / sigma
        charm = -norm.pdf(d1) * (r / (sigma * np.sqrt(T)) - d2 / (2 * T))
        
        term1 = -norm.pdf(d1) / (2 * S * T * sigma * np.sqrt(T))
        term2 = 1 + (2 * r * T * d1 - d2 * sigma * np.sqrt(T)) / (sigma * np.sqrt(T))
        color = term1 * term2
        
        return np.round(delta, 3), np.round(gamma, 4), np.round(vanna, 4), np.round(charm, 4), np.round(color, 6)
    except Exception as e:
        notify_error_sync("MATH_GREEKS_VEC", e, "Critical math failure in vectorized Black-Scholes.")
        return np.zeros_like(S), np.zeros_like(S), np.zeros_like(S), np.zeros_like(S), np.zeros_like(S)

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
    except Exception as e:
        notify_error_sync("MATH_VOL_SURFACE", e, "Failed to map volatility surface.")
        return 0, 0, "NEUTRAL"

def map_vanna_charm_exposures(df):
    """
    Tier-3: 3D Exposure Mapping.
    Calculates total dollar-gamma sensitivity to IV (Vanna) and Time (Charm).
    """
    if df.empty: return 0, 0
    try:
        df['vanna_exp'] = df['vanna'] * df['openInterest'] * 100 * df['underlying_price'] * 0.01
        df['charm_exp'] = df['charm'] * df['openInterest'] * 100
        return df['vanna_exp'].sum(), df['charm_exp'].sum()
    except Exception as e:
        notify_error_sync("MATH_VANNA_CHARM", e, "Failed to map Vanna/Charm exposures.")
        return 0, 0

def map_gex_walls(df):
    if df.empty: return 0, 0, 0
    try:
        df['net_gex'] = np.where(df['side'] == 'calls', 
                                 df['gamma'] * df['openInterest'] * 100 * df['underlying_price'],
                                 -df['gamma'] * df['openInterest'] * 100 * df['underlying_price'])
        
        strike_gex = df.groupby('strike')['net_gex'].sum()
        call_wall, put_wall = strike_gex.idxmax(), strike_gex.idxmin()
        
        flip, strike_gex_sorted = 0, strike_gex.sort_index()
        for i in range(len(strike_gex_sorted)-1):
            if np.sign(strike_gex_sorted.iloc[i]) != np.sign(strike_gex_sorted.iloc[i+1]):
                flip = strike_gex_sorted.index[i]
                break
        return call_wall, put_wall, flip
    except Exception as e:
        notify_error_sync("MATH_GEX_WALLS", e, "Failed to map GEX Walls/Flip Point.")
        return 0, 0, 0

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
    except Exception as e:
        notify_error_sync("MATH_HVN", e, "Failed to calculate HVN conviction.")
        return 1.0, "N/A"

def predict_trend_probability(df_1m, call_wall, put_wall):
    if df_1m is None or len(df_1m) < 30: return 0.5
    try:
        last_p = df_1m['Close'].iloc[-1]
        vwap = df_1m['VWAP'].iloc[-1]
        vwap_std = df_1m['Close'].rolling(window=30).std().iloc[-1]
        z = abs(last_p - vwap) / (vwap_std + 0.01)
        dist_wall = min(abs(last_p - call_wall), abs(last_p - put_wall)) / last_p
        wall_mult = 1.5 if dist_wall < 0.01 else 1.0
        return round(min(0.99, norm.cdf(z) * wall_mult), 2)
    except Exception as e:
        notify_error_sync("MATH_TREND_PROB", e, "Failed to predict trend probability.")
        return 0.5

def detect_icebergs(df_1m):
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
    except Exception as e:
        notify_error_sync("MATH_ICEBERG", e, "Failed to detect iceberg orders.")
        return False

def detect_microstructure_conviction(df_1m):
    if df_1m is None or len(df_1m) < 30: return "Standard", 0
    try:
        if detect_icebergs(df_1m): return "Institutional ICEBERG", 65
        last_c = df_1m.iloc[-1]
        buyer_agg = (last_c['Close'] - last_c['Low']) / (last_c['High'] - last_c['Low'] + 0.01)
        vwap = df_1m['VWAP'].iloc[-1] if 'VWAP' in df_1m.columns else last_c['Close']
        if buyer_agg > 0.8 and last_c['Close'] > vwap: return "🚀 AGGRESSIVE SWEEP 🚀", 50
        return "Passive Flow", 10
    except Exception as e:
        notify_error_sync("MATH_MICROSTRUCTURE", e, "Failed to analyze microstructure conviction.")
        return "Unknown", 0

def classify_aggression(last_price, bid, ask):
    if last_price >= ask and ask > 0: return "Aggressive (Ask)", 50
    if last_price <= bid and bid > 0: return "Passive (Bid)", 0
    return "Neutral (Mid)", 10

def score_unusual(df, ticker, stock_z, sector="Unknown", candle_df=None, social_vel=0.0, earnings_date=None, congress_tickers=None, regime="NEUTRAL"):
    try:
        if df.empty: return pd.DataFrame()
        skew, contango, vol_bias = calculate_volatility_surface(df)
        is_congress_buy = ticker in (congress_tickers or [])

        # Pillar 3: Sector Divergence Check
        divergence = get_sector_divergence(ticker, sector)
        
        baseline = get_ticker_baseline(ticker)
        trust_mult = baseline.get('trust_score', 1.0) if baseline else 1.0
        avg_social = baseline.get('avg_social_vel', 0.0) if baseline else 0.0
        hype_z = (social_vel / (avg_social + 0.1)) if avg_social > 0 else 0.0
        
        weekly_calls = get_weekly_campaign_stats(ticker, 'CALLS')
        weekly_puts = get_weekly_campaign_stats(ticker, 'PUTS')

        T_vec = df['dte'].values / 365.0
        S_vec = df['underlying_price'].values
        K_vec = df['strike'].values
        sigma_vec = df['impliedVolatility'].values
        
        calls, puts = df['side'] == 'calls', df['side'] == 'puts'
        df['delta'], df['gamma'], df['vanna'], df['charm'], df['color'] = 0.0, 0.0, 0.0, 0.0, 0.0
        
        if any(calls):
            d, g, v, c, color = calculate_greeks_vec(S_vec[calls], K_vec[calls], T_vec[calls], 0.045, sigma_vec[calls], 'calls')
            df.loc[calls, ['delta', 'gamma', 'vanna', 'charm', 'color']] = np.stack([d, g, v, c, color], axis=1)
        if any(puts):
            d, g, v, c, color = calculate_greeks_vec(S_vec[puts], K_vec[puts], T_vec[puts], 0.045, sigma_vec[puts], 'puts')
            df.loc[puts, ['delta', 'gamma', 'vanna', 'charm', 'color']] = np.stack([d, g, v, c, color], axis=1)

        df['gex'] = df['gamma'] * df['openInterest'] * 100 * df['underlying_price']
        df['decay_vel'] = df['color'] * df['openInterest'] * 100
        
        call_wall, put_wall, flip = map_gex_walls(df)
        total_vanna, total_charm = map_vanna_charm_exposures(df)
        total_decay_vel = int(df['decay_vel'].sum())
        spot = df.iloc[0]['underlying_price']
        
        micro_label, micro_bonus = detect_microstructure_conviction(candle_df)
        trend_p = predict_trend_probability(candle_df, call_wall, put_wall)
        
        earnings_bonus, days_to_earnings = 0, -1
        if earnings_date:
            try:
                e_date = datetime.strptime(earnings_date, '%Y-%m-%d').date()
                days_to_earnings = (e_date - datetime.now().date()).days
                if 0 <= days_to_earnings <= 7: earnings_bonus = 50 
            except: pass
        
        # SEC GHOST FILING AUDIT
        sec_label, sec_bonus = "Normal Activity", 0
        if any(df['volume'] > 500) or stock_z > 2.0:
            filings = get_sec_filings(ticker)
            if filings:
                last_f = filings[0]
                f_date = datetime.strptime(last_f['date'], '%Y-%m-%d').date()
                days_ago = (datetime.now().date() - f_date).days
                if days_ago <= 5:
                    if last_f['form'] == '4': sec_label, sec_bonus = "🔥 CEO/Insider Just Bought", 50
                    else: sec_label, sec_bonus = "🐋 Major Whale Just Bought 5%+", 50
                else:
                    form_name = "Insider Buy" if last_f['form'] == '4' else "Whale Disclosure"
                    sec_label = f"Last {form_name}: {last_f['date']}"
            else:
                sec_label = "👻 Stealth: No recent disclosures (90d+)"
                update_trust_score(ticker, 0.05) 

        results = []
        for _, row in df.iterrows():
            agg_label, agg_bonus = classify_aggression(row['lastPrice'], row['bid'], row['ask'])
            hvn_conv, hvn_label = calculate_hvn_conviction(candle_df, row['side'].upper(), spot)
            iv, expiration = row.get('impliedVolatility', 0), row.get('exp') or row.get('expiration') or "N/A"
            
            score = 0
            if row['volume'] > 1000: score += 20
            if row['notional'] > 500000: score += 40
            score += agg_bonus + micro_bonus + earnings_bonus + sec_bonus
            
            # Pillar 1: Dynamic Regime Weights
            if regime == "RISK_OFF" and row['side'] == 'puts': score += 30 
            if regime == "RISK_ON" and row['side'] == 'calls': score += 20 
            if regime == "HIGH_VOLATILITY": score -= 20 

            # Pillar 3: Divergence Bonus
            if divergence == "Relative Strength" and row['side'] == 'calls': score += 55
            if divergence == "Isolated Weakness" and row['side'] == 'puts': score += 55
            
            # Pillar 2: Recursive Pattern Memory Bonus
            pattern_avg_p_l = get_matching_patterns(row['gex'], row['vanna'], skew)
            if pattern_avg_p_l > 15: score += 40 
            elif pattern_avg_p_l < -10: score -= 30 

            if is_congress_buy and row['side'] == 'calls': score += 60
            if total_vanna > 500000 and row['side'] == 'calls' and skew < -0.05: score += 45
            if trend_p > 0.85: score += 30 
            if (vol_bias == "BULLISH" and row['side'] == 'calls') or (vol_bias == "BEARISH" and row['side'] == 'puts'): score += 40
            
            campaign_count = weekly_calls if row['side'] == 'calls' else weekly_puts
            if campaign_count >= 3: score += 40
            if campaign_count >= 5: score += 60

            score = int(score * trust_mult * hvn_conv)
            if (row['volume'] > row['openInterest'] and row['volume'] > 500) or score >= 85:
                results.append({
                    'ticker': ticker, 'contract': row['contractSymbol'], 'type': row['side'].upper(),
                    'strike': row['strike'], 'exp': expiration, 'volume': int(row['volume']),
                    'oi': int(row['openInterest']), 'premium': round(row['lastPrice'], 2),
                    'notional': int(row['notional']), 'rel_vol': round(row['volume']/(get_stats(ticker, row['contractSymbol'])['avg_vol']+1), 1),
                    'delta': row['delta'], 'gamma': row['gamma'], 'vanna': row['vanna'], 'charm': row['charm'],
                    'gex': int(row['gex']), 'vanna_exp': int(total_vanna), 'charm_exp': int(total_charm),
                    'decay_vel': total_decay_vel, 'call_wall': call_wall, 'put_wall': put_wall, 'flip': flip,
                    'skew': skew, 'bias': vol_bias, 'score': score, 'trend_prob': trend_p,
                    'aggression': f"{agg_label} | {micro_label} | {hvn_label}",
                    'sector': sector, 'bid': row['bid'], 'ask': row['ask'], 'underlying_price': spot,
                    'sec_signal': sec_label, 'hype_z': round(hype_z, 1),
                    'earnings_dte': days_to_earnings, 'weekly_count': campaign_count,
                    'regime': regime, 'divergence': divergence,
                    'detection_reason': f"Score {score} | {regime} | {divergence}"
                })
        return pd.DataFrame(results)
    except Exception as e:
        notify_error_sync("SCANNER_SCORE", e, f"Critical failure in unusual scoring for {ticker}.")
        return pd.DataFrame()

def generate_system_verdict(trade):
    try:
        t_type, spot, regime = trade['type'], trade.get('underlying_price', 0), trade.get('regime', "NEUTRAL")
        vanna_exp, skew, agg, trend_p = trade.get('vanna_exp', 0), trade.get('skew', 0), trade.get('aggression', ""), trade.get('trend_prob', 0.5)
        e_dte, w_count, sec = trade.get('earnings_dte', -1), trade.get('weekly_count', 0), trade.get('sec_signal', "")
        
        verdict, logic = "NEUTRAL", "Low conviction."
        
        if trade.get('divergence') == "Relative Strength" and "CALL" in t_type:
            return "IDIOSYNCRATIC ALPHA (Long)", "Stock is outperforming its sector. Pure institutional conviction."

        if "GHOST ECHO" in sec:
            verdict, logic = f"{t_type} (Insider Echo)", f"Aggressive flow mirroring recent SEC filing. High institutional conviction."
            return verdict, logic

        if vanna_exp > 750000 and "CALL" in t_type and skew < -0.05:
            verdict, logic = "VANNA SLINGSHOT (Long)", "High Vanna + IV Crush imminent. Dealers forced to BUY to maintain hedges."
            return verdict, logic
            
        if abs(trade.get('charm_exp', 0)) > 1000000 and "PUT" in t_type and spot < trade.get('flip', 0):
            verdict, logic = "CHARM BLEED (Short)", "Massive Delta decay. Dealers forced to SELL as time to expiry decreases."
            return verdict, logic

        if "CALL" in t_type and "Aggressive" in agg:
            if w_count >= 3: verdict, logic = "CALL (Long)", f"Active Weekly Campaign ({w_count} alerts). Massive institutional scaling."
            elif 0 <= e_dte <= 7: verdict, logic = "CALL (Long)", f"Earnings Front-Running ({e_dte}d). High Gamma setup."
            elif trend_p > 0.8: verdict, logic = "CALL (Long)", f"Aggressive sweep + Trend Prob ({trend_p*100}%)."
            elif skew < -0.05: verdict, logic = "CALL (Long)", "Aggressive sweep + Bullish Skew."
            elif spot > 0 and trade.get('put_wall', 0) > 0 and (spot - trade['put_wall']) / spot < 0.02: verdict, logic = "CALL (Long)", "Support bounce at Put Wall."
            else: verdict, logic = "BUY (Stock)", "Bullish flow, conservative tech."
        elif "PUT" in t_type and "Aggressive" in agg:
            if w_count >= 3: verdict, logic = "PUT (Short)", f"Active Weekly Campaign ({w_count} alerts). Bearish institutional scaling."
            elif 0 <= e_dte <= 7: verdict, logic = "PUT (Short)", f"Earnings Front-Running ({e_dte}d). Bearish insider flow."
            elif trend_p > 0.8: verdict, logic = "PUT (Short)", f"Aggressive sweep + Trend Prob ({trend_p*100}%)."
            else: verdict, logic = "PUT (Short)", "Bearish flow detected."
        elif "Dark Pool" in agg or "ICEBERG" in agg: verdict, logic = "BUY (Stock)", "Institutional absorption."
        return verdict, logic
    except Exception as e:
        notify_error_sync("SCANNER_VERDICT", e, f"Logic failure in trade verdict generation.")
        return "NEUTRAL", "Logic failure."

def process_results(all_results, macro_context, sector_performance):
    try:
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
    except Exception as e:
        notify_error_sync("SCANNER_PROCESS", e, "Critical failure during spread/cluster linking.")
        return all_results
