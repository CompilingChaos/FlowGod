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
        
        # RAG Memory Ingestion (Tier-3)
        rag_precedent = get_rag_context(trade['ticker'], trade['type'])

        prompt = f"""You are a Professional Trading Mentor. Explain this institutional flow in SIMPLE, PLAIN LANGUAGE.

DATA:
- TICKER: {trade['ticker']} | Current Price: ${trade['underlying_price']}
- TRADE: {trade['type']} {trade['strike']} | Exp: {trade['exp']}
- CAMPAIGN: {trade.get('weekly_count', 0)} alerts this week.
- TREND PROBABILITY: {trade.get('trend_prob', 0)*100:.0f}%
- LEVELS: Ceiling ${trade['call_wall']} | Floor ${trade['put_wall']}
- EARNINGS: {trade.get('earnings_date', 'N/A')} ({trade.get('earnings_dte', -1)} days away)
- SEC SIGNAL: {trade.get('sec_signal', 'N/A')}

HISTORICAL RAG MEMORY:
{rag_precedent}

TICKER CONTEXT (LAST 48H):
{ticker_context}

MACRO MARKET CONTEXT:
- SPY: {m['spy']}% | VIX: {m['vix']}% | DXY: {m['dxy']}%
- SENTIMENT: {m['sentiment']}

AI INSTRUCTIONS:
1. Check if the SEC SIGNAL confirms insider conviction (e.g. GHOST ECHO).
2. Identify if this trade is a REPEAT of a winning pattern based on RAG Memory.
3. Determine if this ticker is being "Accumulated" (persistent spikes in Context) or is an isolated event.
4. Factor in Macro Sentiment: Is this "Risk-On" flow or a defensive hedge?
5. Explain WHY this is happening (e.g., "Whales are betting on a big move before earnings").
6. Explain the TARGET: Where should I look to take profit based on the Ceiling/Floor?
7. Validate SYSTEM VERDICT: {sys_verdict}. Suggest BUY, CALL, PUT, or NEUTRAL.

RESPONSE SCHEMA (JSON ONLY):
{{
  "is_unusual": boolean,
  "confidence_score": integer (0-100),
  "final_verdict": "BUY" | "CALL" | "PUT" | "NEUTRAL",
  "estimated_duration": "string",
  "verdict_reasoning": "Simple explanation of the verdict",
  "category": "e.g. Earnings Bet | Institutional Accumulation | Bullish Skew",
  "analysis": "Simple overview of why this pattern matters"
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
SEC Signal: {trade.get('sec_signal', 'N/A')}
Earnings: {trade.get('earnings_date', 'N/A')} ({trade.get('earnings_dte', -1)} days)

📢 CAMPAIGN:
Weekly Alerts: {trade.get('weekly_count', 0)}x ({'Institutional Scaling' if trade.get('weekly_count', 0) >= 3 else 'Isolated Trade'})

💬 SOCIAL SENTIMENT:
Hype Status: { '❄️ Cold (Pure Whale Flow)' if trade.get('hype_z', 0) <= 1.0 else '🌡️ Lukewarm (Retail Following)' if trade.get('hype_z', 0) <= 2.5 else '🔥 Overheated (FOMO Trap)' } (Z: {trade.get('hype_z', 0)})

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
