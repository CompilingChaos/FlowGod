import os
import random
import asyncio
import json
import discord
import google.generativeai as genai
from googlesearch import search
from telegram import Bot
from dotenv import load_dotenv
import time

load_dotenv()

# Config
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEYS = [k.strip() for k in os.getenv('GEMINI_API_KEYS', '').split(',') if k.strip()]
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
PROCESSED_FILE = 'processed_messages.json'

# Initialize Telegram
tg_bot = Bot(token=TELEGRAM_TOKEN)

async def analyze_with_ai_retry(trade_content, news_context):
    """Tries all available Gemini API keys with a delay on failure."""
    keys = list(GEMINI_API_KEYS)
    random.shuffle(keys)
    
    prompt = f"""
    Analyze this Unusual Whales trade report:
    {trade_content}

    News Context:
    {news_context}

    Task:
    1. Is this a potential insider trade? (Give a conviction score 1-10)
    2. How meaningful is the size vs daily volume?
    3. What direction should I bid (Long/Short)?
    4. What is the recommended leverage (e.g., 5x, 10x)?
    5. Briefly explain why.

    Format the output for Telegram (Markdown).
    """

    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-3.1-flash')
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Key {key[:8]}... failed: {e}. Trying next key in 5s...")
            await asyncio.sleep(5)
    
    return "Error: All Gemini API keys failed or were rate-limited."

def fetch_news(ticker):
    try:
        query = f"{ticker} stock news insider"
        results = list(search(query, num_results=5, lang="en"))
        return "\n".join(results)
    except:
        return "No recent news found."

async def process_message(message):
    trade_info = f"Author: {message.author}\nContent: {message.content}\n"
    if message.embeds:
        for e in message.embeds:
            trade_info += f"Embed: {e.title} - {e.description}\n"
    
    # Extract ticker (simple heuristic)
    ticker = "SPY" 
    words = trade_info.replace('$', '').split()
    for word in words:
        if word.isupper() and 1 < len(word) < 6:
            ticker = word
            break
            
    news = fetch_news(ticker)
    analysis = await analyze_with_ai_retry(trade_info, news)
    
    final_msg = f"🚀 *FlowGod Analysis: {ticker}*\n\n{analysis}"
    try:
        await tg_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=final_msg, parse_mode='Markdown')
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
        
        # Load processed IDs
        if os.path.exists(PROCESSED_FILE):
            with open(PROCESSED_FILE, 'r') as f:
                processed = json.load(f)
        else:
            processed = []

        new_processed = []
        for guild in client.guilds:
            for channel in guild.text_channels:
                channel_name = channel.name.lower()
                if "unusual" in channel_name or "whale" in channel_name or "flow" in channel_name:
                    print(f"Checking channel: {channel.name}")
                    async for message in channel.history(limit=10):
                        if message.id not in processed:
                            print(f"Processing message {message.id}...")
                            await process_message(message)
                            new_processed.append(message.id)
        
        # Save new IDs
        with open(PROCESSED_FILE, 'w') as f:
            json.dump(processed + new_processed, f)
            
        await client.close()

    await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
