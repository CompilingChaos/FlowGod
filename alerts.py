import asyncio
import os
import logging
from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
import google.generativeai as genai

# Google AI Studio (Gemini) Setup
def get_ai_summary(trade, ticker_context=""):
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return ""
        
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-3-flash")
        
        prompt = f"""As a whale trade analyst, analyze this option trade:
{trade['ticker']} {trade['type']} {trade['strike']} exp {trade['exp']} 
Volume: {trade['volume']} (vs normal {trade['rel_vol']}x)
Notional Value: ${trade['notional']:,}
Z-Score: {trade['z_score']}
IV: {trade['iv']*100:.1f}%

HISTORICAL CONTEXT (Last 2 Days):
{ticker_context}

CRITICAL INSTRUCTIONS:
1. Identify 'Urgency Shifts': Look for a sudden burst of activity compared to the history.
2. If this trade is routine, a small lottery play, or not a true shift in sentiment, reply ONLY with "NOT_UNUSUAL".
3. If it represents high conviction or a significant catalyst-driven sweep, provide a ONE SHORT sentence analysis.
Focus on: 'Lottery play', 'Hedge', or 'Deep Conviction'."""

        response = model.generate_content(prompt)
        text = response.text.strip()
        
        if "NOT_UNUSUAL" in text.upper():
            return "SKIP_ALERT"
            
        return f"\n🧠 AI ANALYST: {text}"
    except Exception as e:
        logging.error(f"Gemini failed: {e}")
        return ""

async def send_alert(trade, ticker_context=""):
    """Sends alert to Telegram with historical context."""
    ai_msg = get_ai_summary(trade, ticker_context)
    
    if ai_msg == "SKIP_ALERT":
        logging.info(f"AI Filtered out {trade['ticker']} as not unusual based on history.")
        return False 
        
    bot = Bot(token=TELEGRAM_TOKEN)
    msg = f"""🚨 WHALE ALERT 🚨
{trade['ticker']} {trade['type']} {trade['strike']} {trade['exp']}
Vol: {trade['volume']} • Notional: ${trade['notional']:,}
Score: {trade['score']} • RelVol: {trade['rel_vol']}x • Z: {trade['z_score']}
IV: {trade['iv']*100:.1f}% • Premium: ${trade['premium']}

📊 CONTEXT (Last 2 Days):
{ticker_context}
{ai_msg}"""

    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        return True
    except Exception as e:
        logging.error(f"Telegram failed: {e}")
        return False
