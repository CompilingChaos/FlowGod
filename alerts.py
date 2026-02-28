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
        m = macro_context or {'spy_pc': 0, 'vix_pc': 0, 'sentiment': "Neutral"}
        macro_str = f"Market Sentiment: {m['sentiment']} (SPY: {m['spy_pc']}%, VIX: {m['vix_pc']}% change)"

        prompt = f"""As an institutional options flow expert, analyze this trade and respond ONLY with a JSON object.

TICKER DATA:
{trade['ticker']} {trade['type']} {trade['strike']} exp {trade['exp']} 
Volume: {trade['volume']} (vs normal {trade['rel_vol']}x)
Stock Heat (Z-Score): {trade['stock_z']}
Aggression: {trade['aggression']} (Price: ${trade['premium']} vs Bid: ${trade['bid']} / Ask: ${trade['ask']})
Notional Value: ${trade['notional']:,}
Option Z-Score: {trade['z_score']}
IV: {trade['iv']*100:.1f}%

MACRO ENVIRONMENT:
{macro_str}

HISTORICAL TICKER CONTEXT (Last 2 Days):
{ticker_context}

RESPONSE SCHEMA (JSON ONLY):
{{
  "is_unusual": boolean,
  "confidence_score": integer (1-100),
  "sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
  "category": "Aggressive Accumulation" | "Strategic Hedge" | "Speculative Lottery" | "Routine Flow",
  "analysis": "One short professional sentence",
  "divergence": "Describe any macro/stock divergence (e.g. Bullish bet into Panic)"
}}

If is_unusual is false, the other fields can be minimal."""

        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean potential markdown code blocks from AI response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        
        if not data.get("is_unusual", True):
            return "SKIP_ALERT"
            
        return data
    except Exception as e:
        logging.error(f"Gemini JSON failed: {e} | Raw: {text if 'text' in locals() else 'N/A'}")
        return None

async def send_alert(trade, ticker_context="", macro_context=None):
    """Sends detailed structured alert to Telegram."""
    ai = get_ai_summary(trade, ticker_context, macro_context)
    
    if ai == "SKIP_ALERT":
        logging.info(f"AI Filtered out {trade['ticker']} via JSON logic.")
        return False 
        
    m = macro_context or {'spy_pc': 0, 'vix_pc': 0, 'sentiment': "Neutral"}
    bot = Bot(token=TELEGRAM_TOKEN)
    
    # Visual confidence meter
    stars = "⭐" * (ai['confidence_score'] // 20) if ai else "N/A"
    
    msg = f"""🚨 WHALE ALERT: {trade['ticker']} 🚨
{stars} (Conviction: {ai['confidence_score'] if ai else '??'}%)

📊 TRADE DETAILS:
Type: {trade['type']} {trade['strike']} | Exp: {trade['exp']}
Aggression: {trade['aggression']}
Vol: {trade['volume']:,} | Notional: ${trade['notional']:,}
Premium: ${trade['premium']} | IV: {trade['iv']*100:.1f}%

🔥 HEAT SCORING:
Whale Score: {trade['score']}
Option Z: {trade['z_score']} | RelVol: {trade['rel_vol']}x
Stock Heat Z: {trade['stock_z']}

🌍 MACRO & CONTEXT:
Macro: {m['sentiment']} (SPY {m['spy_pc']}%)
{ticker_context}

🧠 AI ANALYST:
Category: {ai['category'] if ai else 'Unknown'}
Sentiment: {ai['sentiment'] if ai else 'N/A'}
Analysis: {ai['analysis'] if ai else 'Standard high-volume trade.'}
Divergence: {ai['divergence'] if ai else 'None detected.'}"""

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
