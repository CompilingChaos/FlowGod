import asyncio
import os
from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from openai import OpenAI

# Grok (xAI) Client Setup
def get_ai_summary(trade):
    grok_key = os.getenv("GROK_API_KEY")
    if not grok_key:
        return ""
        
    client = OpenAI(
        api_key=grok_key,
        base_url="https://api.x.ai/v1",
    )
    
    prompt = f"""As a whale trade analyst, analyze this option trade in ONE SHORT sentence:
{trade['ticker']} {trade['type']} {trade['strike']} exp {trade['exp']} 
Volume: {trade['volume']} (vs normal {trade['rel_vol']}x)
Notional Value: ${trade['notional']:,}
Moneyness: {trade['bullish'] if trade['bullish'] else 'Bearish'} position.
Focus on if this is a 'Lottery play', 'Hedge', or 'Deep Conviction'."""

    try:
        response = client.chat.completions.create(
            model="grok-2-latest",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50
        )
        return f"\n🧠 AI ANALYST: {response.choices[0].message.content.strip()}"
    except Exception as e:
        print(f"Grok failed: {e}")
        return ""

async def send_alert(trade):
    bot = Bot(token=TELEGRAM_TOKEN)
    ai_msg = get_ai_summary(trade)
    
    msg = f"""🚨 WHALE ALERT 🚨
{trade['ticker']} {trade['type']} {trade['strike']} {trade['exp']}
Vol: {trade['volume']} • Notional: ${trade['notional']:,}
Score: {trade['score']} • RelVol: {trade['rel_vol']}x • Premium: ${trade['premium']}
{ai_msg}"""

    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except Exception as e:
        print(f"Telegram failed: {e}")
