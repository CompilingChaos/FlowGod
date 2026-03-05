import os
import random
import asyncio
import json
import discord
import yfinance as yf
from google import genai
from googlesearch import search
from telegram import Bot
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
from database import init_db, log_trade, get_performance_stats

load_dotenv()
init_db()

# Config
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEYS = [k.strip() for k in os.getenv('GEMINI_API_KEYS', '').split(',') if k.strip()]
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
PROCESSED_FILE = 'processed_messages.json'

# Initialize Telegram
tg_bot = Bot(token=TELEGRAM_TOKEN)

async def analyze_with_ai_retry(trade_content, news_context, stats):
    """Tries all available Gemini API keys with a delay on failure."""
    keys = list(GEMINI_API_KEYS)
    random.shuffle(keys)
    
    prompt = f"""
    Analyze this Unusual Whales trade report:
    {trade_content}

    News Context (Last 48h):
    {news_context}

    Historical Success Context:
    {stats}

    Task:
    1. Is this a potential insider trade? (Give a conviction score 1-10)
    2. How meaningful is the size vs daily volume?
    3. What direction should I bid (Long/Short)?
    4. What is the recommended leverage (e.g., 5x, 10x)?
    5. What is the recommended timeframe to hold this trade (e.g., 24h, 1 week)?
    6. Briefly explain why.

    Format the output for Telegram using HTML tags (<b>, <i>, <code>, <pre>). 
    Do NOT use Markdown. Ensure all tags are properly closed.
    Include a summary of the historical performance.
    """

    for key in keys:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"Key {key[:8]}... failed: {e}. Trying next key in 5s...")
            await asyncio.sleep(5)
    
    return "Error: All Gemini API keys failed or were rate-limited."

def fetch_news(ticker):
    try:
        # Calculate date for the last 48 hours
        yesterday = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        query = f"{ticker} stock news insider after:{yesterday}"
        results = list(search(query, num_results=5, lang="en"))
        return "\n".join(results)
    except Exception as e:
        print(f"News fetch error for {ticker}: {e}")
        return "No recent news found."

async def process_message(message):
    trade_info = f"Author: {message.author}\nContent: {message.content}\n"
    if message.embeds:
        for e in message.embeds:
            trade_info += f"Embed: {e.title} - {e.description}\n"
    
    ticker = "SPY" 
    words = trade_info.replace('$', '').split()
    for word in words:
        if word.isupper() and 1 < len(word) < 6:
            ticker = word
            break
            
    # Fetch current price
    try:
        price_data = yf.Ticker(ticker).history(period="1d")
        entry_price = price_data['Close'].iloc[-1] if not price_data.empty else 0
        await asyncio.sleep(3) # Rate limit protection
    except:
        entry_price = 0

    news = fetch_news(ticker)
    stats = get_performance_stats()
    analysis = await analyze_with_ai_retry(trade_info, news, stats)
    
    # Extract AI recommendations (simplified for demo, should be more robust)
    direction = "LONG" if "Long" in analysis else "SHORT"
    leverage = 5 # Default
    timeframe = "24h" # Default
    
    # Log trade for future validation
    if entry_price > 0:
        log_trade(ticker, direction, leverage, timeframe, entry_price)

    final_msg = f"🚀 <b>FlowGod Analysis: {ticker}</b>\n\n{analysis}\n\n📊 {stats}"
    try:
        await tg_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=final_msg, parse_mode='HTML')
    except Exception as e:
        print(f"Telegram error: {e}")

async def main():
    if not DISCORD_TOKEN or not GEMINI_API_KEYS:
        print("Missing DISCORD_TOKEN or GEMINI_API_KEYS in environment.")
        return

    client = discord.Client(intents=discord.Intents.default())
    
    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}")
        if os.path.exists(PROCESSED_FILE):
            with open(PROCESSED_FILE, 'r') as f:
                processed = json.load(f)
        else:
            processed = []

        new_processed = []
        for guild in client.guilds:
            for channel in guild.text_channels:
                if any(k in channel.name.lower() for k in ["unusual", "whale", "flow"]):
                    async for message in channel.history(limit=10):
                        if message.id not in processed:
                            await process_message(message)
                            new_processed.append(message.id)
        
        with open(PROCESSED_FILE, 'w') as f:
            json.dump(processed + new_processed, f)
        await client.close()

    await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
