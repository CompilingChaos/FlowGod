import asyncio
import os
import logging
import json
from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
import google.generativeai as genai
from historical_db import get_rag_context

def get_ai_summary(trade, ticker_context="", macro_context=None):
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key: return None
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-3-flash")
        
        m = macro_context or {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'qqq': 0, 'sentiment': "Neutral"}
        macro_str = f"Market: {m['sentiment']} (SPY: {m['spy']}%, DXY: {m['dxy']}%, TNX: {m['tnx']}%)"
        
        # Retrieval-Augmented Context
        rag_context = get_rag_context(trade['ticker'], trade['type'])

        prompt = f"""As an institutional flow expert, analyze this trade using the RUBRIC.

TICKER: {trade['ticker']} {trade['type']} {trade['strike']} | Exp: {trade['exp']}
{macro_str}
{rag_context}

TRADE SPECS:
Vol: {trade['volume']} | Premium: ${trade['premium']} | Aggression: {trade['aggression']}
Delta: {trade['delta']} | Gamma: {trade['gamma']} | GEX: ${trade['gex']:,}
Volatility: Skew is {trade['skew']} ({trade['bias']} bias)
Technicals: Call Wall: ${trade['call_wall']} | Put Wall: ${trade['put_wall']} | Flip: ${trade['flip']}

RUBRIC (0-20 pts each):
1. SIZE (> $500k = 20)
2. ALPHA (Sweep/Ask/Dark Pool = 20)
3. HEDGING (Gamma Squeeze/Wall break = 20)
4. BIAS (Direction matches Skew/Macro = 20)
5. RAG (High historical winrate = 20)

RESPONSE SCHEMA (JSON ONLY):
{{
  "is_unusual": boolean,
  "confidence_score": integer,
  "rubric": {{ "size": int, "alpha": int, "hedge": int, "bias": int, "rag": int }},
  "category": "Aggressive Accumulation" | "Strategic Hedge" | "Speculative Lottery",
  "analysis": "Professional 1-sentence summary"
}}"""

        response = model.generate_content(prompt)
        text = response.text.strip()
        if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except: return None

async def send_alert(trade, ticker_context="", macro_context=None):
    ai = get_ai_summary(trade, ticker_context, macro_context)
    if ai and not ai.get("is_unusual", True): return False
    
    m = macro_context or {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'qqq': 0, 'sentiment': "Neutral"}
    bot = Bot(token=TELEGRAM_TOKEN)
    stars = "⭐" * (ai['confidence_score'] // 20) if ai else "N/A"
    rb = ai.get('rubric', {}) if ai else {}
    
    msg = f"""🚨 FLOWGOD ALPHA: {trade['ticker']} 🚨
{stars} (Conviction: {ai['confidence_score'] if ai else '??'}%)

📊 TRADE DETAILS:
Type: {trade['type']} {trade['strike']} | Exp: {trade['exp']}
Agg: {trade['aggression']}
Vol: {trade['volume']:,} | Notional: ${trade['notional']:,}

📐 GEX & WALLS:
GEX Pressure: ${trade['gex']:,}
Call Wall: ${trade['call_wall']} | Put Wall: ${trade['put_wall']}
Gamma Flip: ${trade['flip']}

🌊 VOL SURFACE:
Skew: {trade['skew']} ({trade['bias']} Bias)

🧠 AI ANALYST:
Category: {ai['category'] if ai else 'Unknown'}
Rubric: S:{rb.get('size',0)} A:{rb.get('alpha',0)} H:{rb.get('hedge',0)} B:{rb.get('bias',0)} R:{rb.get('rag',0)}
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
Position on {contract} was HELD overnight (+{oi_change:,} OI)."""
    try: await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except: pass
