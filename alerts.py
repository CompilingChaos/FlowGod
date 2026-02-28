import asyncio
import os
from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
import google.generativeai as genai

# Google AI Studio (Gemini) Setup
def get_ai_summary(trade):
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return ""
        
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-3-flash")
        
        prompt = f"""As a whale trade analyst, analyze this option trade in ONE SHORT sentence:
{trade['ticker']} {trade['type']} {trade['strike']} exp {trade['exp']} 
Volume: {trade['volume']} (vs normal {trade['rel_vol']}x)
Notional Value: ${trade['notional']:,}
Moneyness: {trade['bullish'] if trade['bullish'] else 'Bearish'} position.
Focus on if this is a 'Lottery play', 'Hedge', or 'Deep Conviction'."""

        response = model.generate_content(prompt)
        return f"\n🧠 AI ANALYST: {response.text.strip()}"
    except Exception as e:
        print(f"Gemini failed: {e}")
        return ""

async def send_alert(trade):
    bot = Bot(token=TELEGRAM_TOKEN)
    ai_msg = get_ai_summary(trade)
    
    msg = f"""🚨 WHALE ALERT 🚨
{trade['ticker']} {trade['type']} {trade['strike']} {trade['exp']}
Vol: {trade['volume']} • Notional: ${trade['notional']:,}
Score: {trade['score']} • RelVol: {trade['rel_vol']}x • Z: {trade['z_score']}
IV: {trade['iv']*100:.1f}% • Premium: ${trade['premium']}
{ai_msg}"""

    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except Exception as e:
        print(f"Telegram failed: {e}")
