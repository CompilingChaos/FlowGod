import asyncio
import os
import logging
from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
import google.generativeai as genai

# Google AI Studio (Gemini) Setup
def get_ai_summary(trade, ticker_context="", macro_context=None):
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return ""
        
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-3-flash")
        
        # Format Macro Context
        m = macro_context or {'spy_pc': 0, 'vix_pc': 0, 'sentiment': "Neutral"}
        macro_str = f"Market Sentiment: {m['sentiment']} (SPY: {m['spy_pc']}%, VIX: {m['vix_pc']}% change)"

        prompt = f"""As an institutional options flow expert, analyze this high-conviction trade:

TICKER DATA:
{trade['ticker']} {trade['type']} {trade['strike']} exp {trade['exp']} 
Volume: {trade['volume']} (vs normal {trade['rel_vol']}x)
Stock Heat (Z-Score): {trade['stock_z']}
Notional Value: ${trade['notional']:,}
Option Z-Score: {trade['z_score']}
IV: {trade['iv']*100:.1f}%

MACRO ENVIRONMENT:
{macro_str}

HISTORICAL TICKER CONTEXT (Last 2 Days):
{ticker_context}

ANALYST INSTRUCTIONS:
1. Determine if this is 'Aggressive Accumulation', a 'Strategic Hedge', or a 'Speculative Lottery'.
2. Look for Bullish/Bearish Divergence: Is the whale betting AGAINST the macro sentiment? (High conviction).
3. If this is routine noise or small relative to the ticker's history, reply ONLY with "NOT_UNUSUAL".
4. If it is significant, provide a ONE SHORT sentence analysis that sounds professional and definitive.
Example: 'Massive bullish divergence; whale betting on recovery despite macro fear.'"""

        response = model.generate_content(prompt)
        text = response.text.strip()
        
        if "NOT_UNUSUAL" in text.upper():
            return "SKIP_ALERT"
            
        return f"\n🧠 AI ANALYST: {text}"
    except Exception as e:
        logging.error(f"Gemini failed: {e}")
        return ""

async def send_alert(trade, ticker_context="", macro_context=None):
    """Sends alert to Telegram with historical and macro context."""
    ai_msg = get_ai_summary(trade, ticker_context, macro_context)
    
    if ai_msg == "SKIP_ALERT":
        logging.info(f"AI Filtered out {trade['ticker']} as not unusual based on history/macro.")
        return False 
        
    m = macro_context or {'spy_pc': 0, 'vix_pc': 0, 'sentiment': "Neutral"}
    bot = Bot(token=TELEGRAM_TOKEN)
    
    msg = f"""🚨 WHALE ALERT 🚨
{trade['ticker']} {trade['type']} {trade['strike']} {trade['exp']}
Vol: {trade['volume']} • Notional: ${trade['notional']:,}
Score: {trade['score']} • RelVol: {trade['rel_vol']}x • Z: {trade['z_score']}
Stock Heat Z: {trade['stock_z']}
IV: {trade['iv']*100:.1f}% • Premium: ${trade['premium']}

🌍 MACRO: {m['sentiment']} (SPY {m['spy_pc']}%)
📊 CONTEXT (Last 2 Days):
{ticker_context}
{ai_msg}"""

    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        return True
    except Exception as e:
        logging.error(f"Telegram failed: {e}")
        return False
