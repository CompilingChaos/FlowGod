import asyncio
import os
import logging
import json
from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
import google.generativeai as genai

# Google AI Studio (Gemini) Setup
def get_ai_summary(trade, ticker_context="", macro_context=None):
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return None
        
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-3-flash")
        
        # Format Macro Context
        m = macro_context or {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'sentiment': "Neutral"}
        macro_str = f"Market: {m['sentiment']} (SPY: {m['spy']}%, VIX: {m['vix']}%, DXY: {m['dxy']}%, TNX: {m['tnx']}%)"

        prompt = f"""As an institutional options flow analyst, evaluate this trade using the STRICT SCORING RUBRIC below.

TICKER DATA:
{trade['ticker']} {trade['type']} {trade['strike']} exp {trade['exp']} 
Volume: {trade['volume']} (vs normal {trade['rel_vol']}x)
Stock Heat (Z-Score): {trade['stock_z']}
Aggression: {trade['aggression']} (Price: ${trade['premium']} vs Bid: ${trade['bid']} / Ask: ${trade['ask']})
Delta: {trade['delta']} | Gamma: {trade['gamma']} | GEX: ${trade['gex']:,}
Notional Value: ${trade['notional']:,}
Option Z-Score: {trade['z_score']}
IV: {trade['iv']*100:.1f}%

MACRO ENVIRONMENT:
{macro_str}

HISTORICAL TICKER CONTEXT:
{ticker_context}

SCORING RUBRIC (Each category is 0-20 points):
1. SIZE: 20pts if notional > $500k, 10pts if > $100k.
2. VOL/OI: 20pts if Vol > OI, 10pts if Vol > 0.5*OI.
3. AGGRESSION: 20pts if 'Sweep/Ask', 10pts if above mid-point.
4. MACRO ALIGNMENT: 20pts if trade direction matches divergence (e.g. Bullish while DXY/TNX dropping).
5. GREEKS/URGENCY: 20pts if High Gamma (>0.05) or ATM Delta (0.45-0.55).

RESPONSE SCHEMA (JSON ONLY):
{{
  "is_unusual": boolean,
  "confidence_score": integer (Sum of the 5 rubric points, 0-100),
  "rubric_breakdown": {{ "size": int, "vol_oi": int, "aggression": int, "macro": int, "greeks": int }},
  "sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
  "category": "Aggressive Accumulation" | "Strategic Hedge" | "Speculative Lottery" | "Routine Flow",
  "analysis": "Standard institutional sentence",
  "divergence": "Describe any macro/stock divergence (e.g. Gamma Squeeze potential)"
}}"""

        response = model.generate_content(prompt)
        text = response.text.strip()
        
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        if not data.get("is_unusual", True):
            return "SKIP_ALERT"
            
        return data
    except Exception as e:
        logging.error(f"Gemini Rubric failed: {e}")
        return None

async def send_alert(trade, ticker_context="", macro_context=None):
    """Sends detailed structured alert with Greeks."""
    ai = get_ai_summary(trade, ticker_context, macro_context)
    
    if ai == "SKIP_ALERT":
        return False 
        
    m = macro_context or {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'sentiment': "Neutral"}
    bot = Bot(token=TELEGRAM_TOKEN)
    
    stars = "⭐" * (ai['confidence_score'] // 20) if ai else "N/A"
    rb = ai['rubric_breakdown'] if ai else {}
    
    msg = f"""🚨 WHALE ALERT: {trade['ticker']} 🚨
{stars} (Conviction: {ai['confidence_score'] if ai else '??'}%)

📊 TRADE DETAILS:
Type: {trade['type']} {trade['strike']} | Exp: {trade['exp']}
Aggression: {trade['aggression']}
Vol: {trade['volume']:,} | Notional: ${trade['notional']:,}
Premium: ${trade['premium']} | IV: {trade['iv']*100:.1f}%

📐 GREEKS & PRESSURE:
Delta: {trade['delta']} | Gamma: {trade['gamma']}
GEX (Dealer Hedge): ${trade['gex']:,}

🔥 HEAT SCORING:
Whale Score: {trade['score']}
Option Z: {trade['z_score']} | RelVol: {trade['rel_vol']}x
Stock Heat Z: {trade['stock_z']}

🌍 MACRO & CONTEXT:
Macro: {m['sentiment']}
DXY: {m['dxy']}% | TNX: {m['tnx']}%
{ticker_context}

🧠 AI ANALYST (Rubric Breakdown):
Size: {rb.get('size',0)} | Vol/OI: {rb.get('vol_oi',0)} | Agg: {rb.get('aggression',0)}
Macro: {rb.get('macro',0)} | Greeks: {rb.get('greeks',0)}

Category: {ai['category'] if ai else 'Unknown'}
Analysis: {ai['analysis'] if ai else 'N/A'}
Divergence: {ai['divergence'] if ai else 'None.'}"""

    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        return True
    except Exception as e:
        logging.error(f"Telegram failed: {e}")
        return False

async def send_confirmation_alert(ticker, contract, oi_change, percentage):
    """Sends a confirmation alert when a whale holds a position overnight."""
    bot = Bot(token=TELEGRAM_TOKEN)
    msg = f"""✅ WHALE CONFIRMED: {ticker} ✅
The institutional position on {contract} was HELD overnight.

📈 OI Change: +{oi_change:,} contracts
🔥 Stickiness: {percentage:.1f}% of yesterday's volume held.
Trust score for {ticker} has been increased."""

    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        return True
    except Exception as e:
        logging.error(f"Telegram confirmation failed: {e}")
        return False
