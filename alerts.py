import asyncio
import os
import logging
import json
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY
from google import genai
from historical_db import get_rag_context
from scanner import generate_system_verdict

def get_ai_summary(trade, ticker_context="", macro_context=None):
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key: return None
    try:
        client = genai.Client(api_key=gemini_key)
        m = macro_context or {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'qqq': 0, 'sentiment': "Neutral"}
        macro_str = f"Market: {m['sentiment']} (SPY: {m['spy']}%, DXY: {m['dxy']}%, TNX: {m['tnx']}%)"
        rag_context = get_rag_context(trade['ticker'], trade['type'])
        sys_verdict, sys_logic = generate_system_verdict(trade)

        prompt = f"""As an institutional flow expert, evaluate this trade and the structural hedging support.

TICKER: {trade['ticker']} {trade['type']} {trade['strike']} | Exp: {trade['exp']}
{macro_str}
{rag_context}

HYPE & SENTIMENT:
Hype Z-Score: {trade.get('hype_z', 0)} (High = Retail FOMO, Low = Institutional Alpha)

GREEKS & DECAY:
Delta: {trade['delta']} | Gamma: {trade['gamma']} | Vanna: {trade['vanna']} | Charm: {trade['charm']}
Hedge Decay Velocity (Color): {trade.get('decay_vel', 0)} (Measures speed of hedging support loss)
GEX Pressure: ${trade['gex']:,} | Gamma Flip Level: ${trade['flip']}

TECHNICALS:
Volatility: Skew is {trade['skew']} ({trade['bias']} bias)
Walls: Call Wall: ${trade['call_wall']} | Put Wall: ${trade['put_wall']}

AI INSTRUCTIONS:
1. Use 'Hedge Decay Velocity' to determine if the structural support for this move is accelerating or nearing a 'Decay Cliff'.
2. Validate SYSTEM VERDICT: {sys_verdict} ({sys_logic}).
3. Suggest duration and entry quality. Respond ONLY with JSON.

RESPONSE SCHEMA:
{{
  "is_unusual": boolean,
  "confidence_score": integer,
  "final_verdict": "BUY" | "CALL" | "PUT" | "NEUTRAL",
  "estimated_duration": "string",
  "verdict_reasoning": "...",
  "analysis": "..."
}}"""

        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        text = response.text.strip()
        if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except: return None

async def send_alert(trade, ticker_context="", macro_context=None):
    ai = get_ai_summary(trade, ticker_context, macro_context)
    if ai and not ai.get("is_unusual", True): return False
    
    bot = Bot(token=TELEGRAM_TOKEN)
    stars = "⭐" * (ai['confidence_score'] // 20) if ai and 'confidence_score' in ai else "N/A"
    
    sys_v, sys_l = generate_system_verdict(trade)
    final_v = ai['final_verdict'] if ai and 'final_verdict' in ai else sys_v
    
    msg = f"""🚨 FLOWGOD ALPHA: {trade['ticker']} 🚨
{stars} (Conviction: {ai['confidence_score'] if ai and 'confidence_score' in ai else '??'}%)

🏁 VERDICT: {final_v}
⏳ EST. DURATION: {ai['estimated_duration'] if ai and 'estimated_duration' in ai else 'Unknown'}
Reasoning: {ai['verdict_reasoning'] if ai and 'verdict_reasoning' in ai else sys_l}

📊 TRADE DETAILS:
Type: {trade['type']} {trade['strike']} | Exp: {trade['exp']}
Agg: {trade['aggression']}
Vol: {trade['volume']:,} | Notional: ${trade['notional']:,}

📐 GREEKS & VELOCITY:
GEX Pressure: ${trade['gex']:,}
Hedge Decay (Color): {trade.get('decay_vel', 0)}
Call Wall: ${trade['call_wall']} | Put Wall: ${trade['put_wall']}
Gamma Flip: ${trade['flip']}

💬 SOCIAL SENTIMENT:
Hype Z-Score: {trade.get('hype_z', 0)} ({'LOUD/FOMO' if trade.get('hype_z',0) > 2 else 'QUIET/ALPHA'})

🧠 AI ANALYST:
Analysis: {ai['analysis'] if ai and 'analysis' in ai else 'N/A'}"""

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
