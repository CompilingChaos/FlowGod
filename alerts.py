import asyncio
import os
import logging
import json
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY
from google import genai
from historical_db import get_rag_context
from scanner import generate_system_verdict

# Modern Google GenAI Client
def get_ai_summary(trade, ticker_context="", macro_context=None):
    if not GEMINI_API_KEY: return None
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        m = macro_context or {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'qqq': 0, 'sentiment': "Neutral"}
        macro_str = f"Market: {m['sentiment']} (SPY: {m['spy']}%, DXY: {m['dxy']}%, TNX: {m['tnx']}%)"
        rag_context = get_rag_context(trade['ticker'], trade['type'])
        sys_verdict, sys_logic = generate_system_verdict(trade)

        prompt = f"""As an institutional flow expert, evaluate this trade.

TICKER: {trade['ticker']} {trade['type']} {trade['strike']} | Exp: {trade['exp']}
{macro_str}
{rag_context}

SYSTEM VERDICT: {sys_verdict}
SYSTEM LOGIC: {sys_logic}

TRADE SPECS:
Vol: {trade['volume']} | Aggression: {trade['aggression']}
Delta: {trade['delta']} | Gamma: {trade['gamma']} | GEX: ${trade['gex']:,}
Volatility: Skew is {trade['skew']} ({trade['bias']} bias)
Technicals: Call Wall: ${trade['call_wall']} | Put Wall: ${trade['put_wall']} | Flip: ${trade['flip']}

AI INSTRUCTIONS:
1. Validate the SYSTEM VERDICT and suggest a Trade Republic compatible action (BUY, CALL, or PUT).
2. ESTIMATE DURATION: How many days/weeks until this trade likely reaches its profit target based on DTE and GEX?
3. Respond ONLY with JSON.

RESPONSE SCHEMA:
{{
  "is_unusual": boolean,
  "confidence_score": integer,
  "final_verdict": "BUY" | "CALL" | "PUT" | "NEUTRAL",
  "estimated_duration": "string (e.g. 2-5 days)",
  "verdict_reasoning": "...",
  "category": "...",
  "analysis": "..."
}}"""

        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        text = response.text.strip()
        if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except: return None

async def send_alert(trade, ticker_context="", macro_context=None, is_shadow=False):
    ai = get_ai_summary(trade, ticker_context, macro_context)
    if ai and not ai.get("is_unusual", True): return False
    
    m = macro_context or {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'qqq': 0, 'sentiment': "Neutral"}
    bot = Bot(token=TELEGRAM_TOKEN)
    stars = "⭐" * (ai['confidence_score'] // 20) if ai and 'confidence_score' in ai else "N/A"
    
    sys_v, sys_l = generate_system_verdict(trade)
    final_v = ai['final_verdict'] if ai and 'final_verdict' in ai else sys_v
    
    shadow_label = "🕵️ SHADOW TRIGGERED 🕵️\n" if is_shadow else ""
    
    msg = f"""🚨 FLOWGOD ALPHA: {trade['ticker']} 🚨
{shadow_label}{stars} (Conviction: {ai['confidence_score'] if ai and 'confidence_score' in ai else '??'}%)

🏁 VERDICT: {final_v}
⏳ EST. DURATION: {ai['estimated_duration'] if ai else 'Unknown'}
Reasoning: {ai['verdict_reasoning'] if ai else sys_l}

📊 TRADE DETAILS:
Type: {trade['type']} {trade['strike']} | Exp: {trade['exp']}
Agg: {trade['aggression']}
Vol: {trade['volume']:,} | Notional: ${trade['notional']:,}

📐 GEX & WALLS:
GEX Pressure: ${trade['gex']:,}
Call Wall: ${trade['call_wall']} | Put Wall: ${trade['put_wall']}
Gamma Flip: ${trade['flip']}

🧠 AI ANALYST:
Category: {ai['category'] if ai and 'category' in ai else 'Unknown'}
Analysis: {ai['analysis'] if ai and 'analysis' in ai else 'N/A'}"""

    # Add "Save Trade" button (Native Callback)
    # We store the core data in the callback string
    # Format: save|TICKER|TYPE|STRIKE|PRICE
    cb_data = f"save|{trade['ticker']}|{trade['type']}|{trade['strike']}|{trade['underlying_price']}"
    keyboard = [[InlineKeyboardButton("💾 SAVE TRADE", callback_data=cb_data)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, reply_markup=reply_markup)
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
