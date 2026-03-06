import asyncio
import json
import os
import random
import hashlib
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup
from datetime import datetime

# URL of the Unusual Whales channel provided by the user
DISCORD_URL = "https://discord.com/channels/710524439133028512/1187484002844680354"
SESSION_FILE = "discord_session.json"
MESSAGES_FILE = "unusual_messages.json"
PROCESSED_FILE = "processed_messages.json"

def get_content_hash(text):
    """Generate a unique hash for message content."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

async def scrape_discord():
    # Load already processed hashes
    processed_hashes = []
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE, 'r') as f:
                processed_data = json.load(f)
                processed_hashes = [get_content_hash(m) if isinstance(m, str) else m for m in processed_data]
        except: pass

    # 1. Random Initial Jitter
    jitter_seconds = random.randint(60, 300)
    print(f"⏳ Humanizing behavior: Sleeping for {jitter_seconds} seconds before scraping...")
    await asyncio.sleep(jitter_seconds)

    if not os.path.exists(SESSION_FILE):
        print(f"❌ Error: {SESSION_FILE} not found.")
        return []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=SESSION_FILE)
        page = await context.new_page()
        
        # Apply stealth plugins
        try:
            stealth_applier = Stealth()
            await stealth_applier.apply_stealth_async(page)
            print("🛡️ Stealth applied successfully.")
        except Exception as e:
            print(f"⚠️ Warning: Stealth application failed. {e}")
        
        print(f"🚀 Navigating to {DISCORD_URL}...")
        await page.goto(DISCORD_URL)
        
        # 2. Variable Load Wait
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(random.uniform(3, 8))
        
        # 3. Simulate mouse movement
        for _ in range(random.randint(2, 5)):
            x, y = random.randint(100, 500), random.randint(100, 500)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.5, 1.5))

        # Wait for the message container
        try:
            await page.wait_for_selector('li[class*="messageListItem"]', timeout=45000)
        except Exception:
            await page.screenshot(path="debug_discord.png")
            await browser.close()
            return []

        # 4. "Reading" delay before starting extraction
        await asyncio.sleep(random.uniform(4, 10))
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        message_items = soup.find_all(['li', 'div'], class_=lambda x: x and 'messageListItem' in x)

        messages_to_process = []
        # Process the last 20 messages to ensure we don't miss anything due to scrolling/loading
        # Deduplication now happens in the main engine via stable IDs
        for item in reversed(message_items[-20:]):
            raw_text = item.get_text(separator=" ").strip()
            # Clean noise
            for n in ["(edited)", "NEW", "Reply", "Pins", "Threads"]: 
                raw_text = raw_text.replace(n, "")
            
            content_text = raw_text.strip()
            if len(content_text) < 30: continue # Ignore tiny system messages or fragments
                
            print(f"✨ Potential message: {content_text[:40]}...")
            messages_to_process.append({
                "content": content_text,
                "timestamp": datetime.now().isoformat()
            })
            
            if len(messages_to_process) >= 15: break

        print(f"✅ Scraped {len(messages_to_process)} raw message units.")
        
        # 6. Linger Exit
        linger_time = random.randint(10, 25)
        print(f"🧘 Lingering for {linger_time}s before closing browser...")
        await asyncio.sleep(linger_time)
        
        await browser.close()
        return messages_to_process

if __name__ == "__main__":
    messages = asyncio.run(scrape_discord())
    if messages:
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(messages, f, indent=4)
