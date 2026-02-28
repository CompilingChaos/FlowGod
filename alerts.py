import asyncio
from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

async def send_alert(trade):
    bot = Bot(token=TELEGRAM_TOKEN)
    msg = f"""🚨 WHALE ALERT 🚨
{trade['ticker']} {trade['type']} {trade['strike']} {trade['exp']}
Vol: {trade['volume']} • Notional: ${trade['notional']:,}
Score: {trade['score']} • RelVol: {trade['rel_vol']}x • Premium: ${trade['premium']}"""
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except:
        print("Telegram failed - check token")
