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
        
        m = macro_context or {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'qqq': 0, 'sentiment': "Neutral"}
        macro_str = f"Market: {m['sentiment']} (SPY: {m['spy']}%, VIX: {m['vix']}%, DXY: {m['dxy']}%, TNX: {m['tnx']}%, QQQ: {m['qqq']}%)"

        prompt = f"""As an institutional options flow analyst, evaluate this trade using the STRICT SCORING RUBRIC below.

TICKER DATA:
{trade['ticker']} {trade['type']} {trade['strike']} exp {trade['exp']} 
Volume: {trade['volume']} (vs normal {trade['rel_vol']}x)
Stock Heat (Z-Score): {trade['stock_z']}
Aggression: {trade['aggression']}
Delta: {trade['delta']} | Gamma: {trade['gamma']} | Vanna: {trade['vanna']} | Charm: {trade['charm']}
GEX (Dealer Hedge): ${trade['gex']:,} | Gamma Flip Level: ${trade['flip']}
Notional Value: ${trade['notional']:,}
Option Z-Score: {trade['z_score']} | IV: {trade['iv']*100:.1f}%

MACRO ENVIRONMENT:
{macro_str}

HISTORICAL TICKER CONTEXT:
{ticker_context}

SCORING RUBRIC (Each category is 0-20 points):
1. SIZE: 20pts if notional > $500k, 10pts if > $100k.
2. VOL/OI: 20pts if Vol > OI, 10pts if Vol > 0.5*OI.
3. AGGRESSION: 20pts if contains 'TRV Max' or 'Ask', 10pts if above mid-point.
4. MACRO/HEDGING: 20pts if Vanna/Charm indicate dealer buy-pressure or macro divergence.
5. TECHNICALS: 20pts if trade is near the Gamma Flip Level (${trade['flip']}).

RESPONSE SCHEMA (JSON ONLY):
{{
  "is_unusual": boolean,
  "confidence_score": integer (Sum of the 5 rubric points, 0-100),
  "rubric_breakdown": {{ "size": int, "vol_oi": int, "aggression": int, "macro_hedge": int, "technicals": int }},
  "sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
  "category": "Aggressive Accumulation" | "Strategic Hedge" | "Speculative Lottery" | "Routine Flow",
  "analysis": "Institutional summary of intent",
  "divergence": "Describe any macro/sector divergence"
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
        logging.error(f"Gemini Alpha Suite failed: {e}")
        return None

async def send_alert(trade, ticker_context="", macro_context=None):
    ai = get_ai_summary(trade, ticker_context, macro_context)
    if ai == "SKIP_ALERT": return False 
        
    m = macro_context or {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'qqq': 0, 'sentiment': "Neutral"}
    bot = Bot(token=TELEGRAM_TOKEN)
    
    stars = "⭐" * (ai['confidence_score'] // 20) if ai else "N/A"
    rb = ai['rubric_breakdown'] if ai else {}
    
    msg = f"""🚨 WHALE ALERT: {trade['ticker']} 🚨
{stars} (Conviction: {ai['confidence_score'] if ai else '??'}%)

📊 TRADE DETAILS:
Type: {trade['type']} {trade['strike']} | Exp: {trade['exp']}
Agg: {trade['aggression']}
Vol: {trade['volume']:,} | Notional: ${trade['notional']:,}
IV: {trade['iv']*100:.1f}%

📐 ADVANCED GREEKS:
Delta: {trade['delta']} | Gamma: {trade['gamma']}
Vanna: {trade['vanna']} | Charm: {trade['charm']}
GEX Pressure: ${trade['gex']:,}
Gamma Flip: ${trade['flip']}

🔥 HEAT SCORING:
Whale Score: {trade['score']} | Trust: {trade['rel_vol']}x
Stock Heat Z: {trade['stock_z']}

🌍 MACRO & RS:
Macro: {m['sentiment']}
DXY: {m['dxy']}% | TNX: {m['tnx']}% | QQQ: {m['qqq']}%
{ticker_context}

🧠 AI ANALYST (Rubric):
Size: {rb.get('size',0)} | Vol/OI: {rb.get('vol_oi',0)} | Agg: {rb.get('aggression',0)}
Hedge: {rb.get('macro_hedge',0)} | Tech: {rb.get('technicals',0)}

Category: {ai['category'] if ai else 'Unknown'}
Analysis: {ai['analysis'] if ai else 'N/A'}"""

    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        return True
    except Exception as e:
        logging.error(f"Telegram failed: {e}")
        return False

async def send_confirmation_alert(ticker, contract, oi_change, percentage):
    bot = Bot(token=TELEGRAM_TOKEN)
    msg = f"""✅ WHALE CONFIRMED: {ticker} ✅
The institutional position on {contract} was HELD overnight.

📈 OI Change: +{oi_change:,} contracts
🔥 Stickiness: {percentage:.1f}% of yesterday's volume held."""

    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        return True
    except Exception as e:
        logging.error(f"Telegram confirmation failed: {e}")
        return False
