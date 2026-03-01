import asyncio
import os
import logging
import json
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY
from google import genai
from historical_db import get_rag_context
from scanner import generate_system_verdict
from error_reporter import notify_error_sync

def get_ai_summary(trade, ticker_context="", macro_context=None):
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key: return None
    try:
        client = genai.Client(api_key=gemini_key)
        m = macro_context or {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'qqq': 0, 'sentiment': "Neutral"}
        sys_verdict, sys_logic = generate_system_verdict(trade)

        prompt = f"""You are a Professional Trading Mentor. Explain this institutional flow in SIMPLE, PLAIN LANGUAGE.

DATA:
- TICKER: {trade['ticker']} | Current Price: ${trade['underlying_price']}
- TRADE: {trade['type']} {trade['strike']} | Exp: {trade['exp']}
- CAMPAIGN: {trade.get('weekly_count', 0)} alerts this week.
- TREND PROBABILITY: {trade.get('trend_prob', 0)*100:.0f}%
- LEVELS: Ceiling ${trade['call_wall']} | Floor ${trade['put_wall']}
- EARNINGS: {trade.get('earnings_date', 'N/A')} ({trade.get('earnings_dte', -1)} days away)

AI INSTRUCTIONS:
1. Explain the situation like I am a student. Avoid complex jargon like 'GEX' or 'Vanna'.
2. Explain WHY this is happening (e.g., "Whales are betting on a big move before earnings").
3. Explain the TARGET: Where should I look to take profit based on the Ceiling/Floor?
4. Validate SYSTEM VERDICT: {sys_verdict}. Suggest BUY, CALL, PUT, or NEUTRAL.

RESPONSE SCHEMA (JSON ONLY):
{{
  "is_unusual": boolean,
  "confidence_score": integer,
  "final_verdict": "BUY" | "CALL" | "PUT" | "NEUTRAL",
  "estimated_duration": "string",
  "verdict_reasoning": "Simple explanation of the verdict",
  "category": "e.g. Earnings Bet",
  "analysis": "Simple overview of the whale activity"
}}"""

        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        text = response.text.strip()
        if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        logging.error(f"AI Summary failed: {e}")
        return None

async def send_alert(trade, ticker_context="", macro_context=None, is_shadow=False):
    try:
        ai = get_ai_summary(trade, ticker_context, macro_context)
        if ai and not ai.get("is_unusual", True): return False

        bot = Bot(token=TELEGRAM_TOKEN)
        stars = "⭐" * (ai['confidence_score'] // 20) if ai and 'confidence_score' in ai else "N/A"

        sys_v, sys_l = generate_system_verdict(trade)
        final_v = ai['final_verdict'] if ai and 'final_verdict' in ai else sys_v

        shadow_label = "🕵️ SHADOW TRIGGERED 🕵️\n" if is_shadow else ""

        msg = f"""🚨 FLOWGOD ALPHA: {trade['ticker']} 🚨
{shadow_label}💎 Current Price: ${trade['underlying_price']:.2f}
{stars} (Conviction: {ai['confidence_score'] if ai and 'confidence_score' in ai else '??'}%)

🏁 VERDICT: {final_v}
📈 TREND PROBABILITY: {trade.get('trend_prob', 0)*100:.0f}%
⏳ EST. DURATION: {ai['estimated_duration'] if ai and 'estimated_duration' in ai else 'Unknown'}
Reasoning: {ai['verdict_reasoning'] if ai and 'verdict_reasoning' in ai else sys_l}

📊 TRADE DETAILS:
Type: {trade['type']} {trade['strike']} | Exp: {trade['exp']}
Agg: {trade['aggression']}
Vol: {trade['volume']:,} | Notional: ${trade['notional']:,}

📐 INSTITUTIONAL LEVELS:
Flow Impact: ${trade['gex']:,}
Timing Quality: {trade.get('decay_vel', 0)}
Major Ceiling: ${trade['call_wall']} | Major Floor: ${trade['put_wall']}
Trend Catalyst: ${trade['flip']}

🗓️ CATALYST:
...

Earnings: {trade.get('earnings_date', 'N/A')} ({trade.get('earnings_dte', -1)} days)

📢 CAMPAIGN:
Weekly Alerts: {trade.get('weekly_count', 0)}x ({'Institutional Scaling' if trade.get('weekly_count', 0) >= 3 else 'Isolated Trade'})

💬 SOCIAL SENTIMENT:
Hype Z-Score: {trade.get('hype_z', 0)} ({'LOUD/FOMO' if trade.get('hype_z',0) > 2 else 'QUIET/ALPHA'})

🧠 AI ANALYST:
Analysis: {ai['analysis'] if ai and 'analysis' in ai else 'N/A'}"""

        cb_data = f"save|{trade['ticker']}|{trade['type']}|{trade['strike']}|{trade['underlying_price']}"
        keyboard = [[InlineKeyboardButton("💾 SAVE TRADE", callback_data=cb_data)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, reply_markup=reply_markup)
        return True
    except Exception as e:
        logging.error(f"Telegram alert failed: {e}")
        notify_error_sync("ALERTS_SEND", e, f"Failed to send alert for {trade['ticker']}")
        return False

async def send_confirmation_alert(ticker, contract, oi_change, percentage):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        msg = f"""✅ WHALE CONFIRMED: {ticker} ✅
Position on {contract} was HELD overnight (+{oi_change:,} OI)."""
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except Exception as e:
        logging.error(f"Confirmation alert failed: {e}")
        notify_error_sync("ALERTS_CONFIRM", e, f"Failed to send confirmation for {ticker}")
