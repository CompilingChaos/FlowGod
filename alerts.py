import asyncio
import os
import logging
import json
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY, GEMINI_API_KEY_FALLBACK
from google import genai
from google.genai import types
from historical_db import get_rag_context
from scanner import generate_system_verdict
from error_reporter import notify_error_sync

def get_ticker_news(ticker, keys):
    """
    Tier-4 Discovery: Real-Time News Grounding.
    Uses Gemini with Google Search to find catalysts from the last 24-48 hours.
    """
    for idx, key in enumerate(keys):
        if not key: continue
        try:
            client = genai.Client(api_key=key)
            # Use Google Search tool for grounding
            google_search_tool = types.Tool(google_search=types.GoogleSearch())
            
            prompt = f"Search for and summarize the most important news for ${ticker} from the last 24 hours. Focus on earnings, rumors, M&A, or analyst upgrades. If no major news exists in the last 24 hours, respond exactly with 'NO_RECENT_NEWS'."
            
            response = client.models.generate_content(
                model="gemini-3-flash-preview", 
                contents=prompt,
                config=types.GenerateContentConfig(tools=[google_search_tool])
            )
            
            news = response.text.strip()
            if "NO_RECENT_NEWS" in news: return "No major news catalysts detected in the last 24 hours."
            return news
        except Exception as e:
            logging.warning(f"News Search attempt {idx+1} failed: {e}")
            continue
    return "News grounding unavailable."

def get_ai_summary(trade, ticker_context="", macro_context=None):
    keys = [GEMINI_API_KEY, GEMINI_API_KEY_FALLBACK]
    
    # Phase 1: Real-Time News Search
    news_context = get_ticker_news(trade['ticker'], keys)
    
    # Phase 2: Final Evaluation
    last_error = None
    for idx, key in enumerate(keys):
        if not key: continue
        try:
            client = genai.Client(api_key=key)
            m = macro_context or {'spy': 0, 'vix': 0, 'dxy': 0, 'tnx': 0, 'qqq': 0, 'sentiment': "Neutral"}
            sys_verdict, sys_logic = generate_system_verdict(trade)
            
            rag_precedent = get_rag_context(trade['ticker'], trade['type'])

            prompt = f"""You are a Professional Trading Mentor. Explain this institutional flow in SIMPLE, PLAIN LANGUAGE.

DATA:
- TICKER: {trade['ticker']} | Current Price: ${trade['underlying_price']}
- TRADE: {trade['type']} {trade['strike']} | Exp: {trade['exp']}
- CAMPAIGN: {trade.get('weekly_count', 0)} alerts this week.
- TREND PROBABILITY: {trade.get('trend_prob', 0)*100:.0f}%
- EARNINGS: {trade.get('earnings_date', 'N/A')} ({trade.get('earnings_dte', -1)} days away)
- SEC SIGNAL: {trade.get('sec_signal', 'N/A')}

RAW QUANTITATIVE METRICS:
- GEX IMPACT: ${trade.get('gex', 0):,} (Dealer Delta hedging pressure)
- VANNA EXPOSURE: ${trade.get('vanna_exp', 0):,} (Sensitivity to Volatility crush)
- CHARM EXPOSURE: {trade.get('charm_exp', 0):,} (Sensitivity to Time decay)
- GREEKS: Delta {trade.get('delta', 0)} | Gamma {trade.get('gamma', 0)}
- INTENSITY: Vol {trade.get('volume', 0):,} vs OI {trade.get('oi', 0):,} (Ratio: {trade.get('rel_vol', 0)}x)
- LEVELS: Ceiling ${trade.get('call_wall', 0)} | Floor ${trade.get('put_wall', 0)} | Flip ${trade.get('flip', 0)}

REAL-TIME NEWS CONTEXT:
{news_context}

HISTORICAL RAG MEMORY:
{rag_precedent}

TICKER CONTEXT (LAST 48H):
{ticker_context}

MACRO MARKET CONTEXT:
- SPY: {m['spy']}% | VIX: {m['vix']}% | DXY: {m['dxy']}%
- SENTIMENT: {m['sentiment']}

AI INSTRUCTIONS:
1. ESTIMATE DURATION: The Expiration Date (Exp) is the MOST important ceiling. Never suggest a duration longer than the DTE.
2. TIMING QUALITY: Use 'Timing Quality' (Decay Velocity) and 'Charm Exposure' to accelerate the estimate. (High Quality = Move expected in 1-3 days).
3. Use the RAW QUANTITATIVE METRICS to determine the true magnitude of the trade.
4. Use the REAL-TIME NEWS CONTEXT to explain WHY this flow is happening.
5. Check if the SEC SIGNAL confirms insider conviction.
6. Validate SYSTEM VERDICT: {sys_verdict}. Suggest BUY, CALL, PUT, or NEUTRAL.

RESPONSE SCHEMA (JSON ONLY):
{{
  "is_unusual": boolean,
  "confidence_score": integer (0-100),
  "final_verdict": "BUY" | "CALL" | "PUT" | "NEUTRAL",
  "estimated_duration": "e.g. 24-48 Hours | 1-2 Weeks | Hold until Expiration",
  "verdict_reasoning": "Simple explanation based on math, news, and timing velocity",
  "category": "e.g. Gamma Squeeze | Insider Echo | Speculative Potential",
  "analysis": "Simple overview of why this pattern matters"
}}"""

            response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
            text = response.text.strip()
            if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except Exception as e:
            last_error = e
            logging.warning(f"Gemini API attempt {idx+1} failed: {e}")
            continue
    
    if last_error:
        logging.error(f"All Gemini API attempts exhausted: {last_error}")
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

        cb_data = f"save|{trade['ticker']}|{trade['type']}|{trade['strike']}|{trade['underlying_price']}|{trade.get('gex',0)}|{trade.get('vanna_exp',0)}|{trade.get('charm_exp',0)}|{trade.get('skew',0)}"
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
