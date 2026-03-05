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
    # Load already processed hashes to avoid redundant work
    processed_hashes = []
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE, 'r') as f:
                processed_data = json.load(f)
                # Handle both raw strings and existing hashes in the list
                processed_hashes = [get_content_hash(m) if isinstance(m, str) else m for m in processed_data]
        except: pass

    # Random jitter: Wait 1 to 5 minutes before starting (SAFETY)
    jitter_seconds = random.randint(60, 300)
    print(f"⏳ Humanizing behavior: Sleeping for {jitter_seconds} seconds before scraping...")
    await asyncio.sleep(jitter_seconds)

    if not os.path.exists(SESSION_FILE):
        print(f"❌ Error: {SESSION_FILE} not found. Run 'python session_manager.py' locally first.")
        return []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=SESSION_FILE)
        page = await context.new_page()
        
        # Apply stealth plugins
        try:
            stealth_applier = Stealth()
            await stealth_applier.apply_stealth_async(page)
            print("🛡️ Stealth applied successfully (apply_stealth_async).")
        except Exception as e:
            print(f"⚠️ Warning: Stealth application failed. {e}")
        
        print(f"🚀 Navigating to {DISCORD_URL}...")
        await page.goto(DISCORD_URL)
        await page.wait_for_load_state("networkidle")
        
        # Wait for the message container
        try:
            await page.wait_for_selector('li[class*="messageListItem"]', timeout=45000)
        except Exception:
            await page.screenshot(path="debug_discord.png")
            await browser.close()
            return []

        # Wait a bit for embeds
        await asyncio.sleep(5)
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        message_items = soup.find_all(['li', 'div'], class_=lambda x: x and 'messageListItem' in x)

        messages_to_process = []
        # Look at the last 12 messages
        # We process from NEWEST to OLDEST (bottom to top)
        for item in reversed(message_items[-12:]):
            raw_text = item.get_text(separator=" ").strip()
            # Clean noise
            for n in ["(edited)", "NEW", "Reply", "Pins", "Threads"]: 
                raw_text = raw_text.replace(n, "")
            
            content_text = raw_text.strip()
            if len(content_text) < 15: continue
            
            msg_hash = get_content_hash(content_text)
            
            # STOP as soon as we hit a message we've seen before
            if msg_hash in processed_hashes:
                print("📍 Reached 'Last Seen' message. Stopping extraction.")
                break
                
            print(f"✨ New message detected: {content_text[:40]}...")
            messages_to_process.append({
                "content": content_text,
                "timestamp": datetime.now().isoformat()
            })
            
            # Simulate "reading" time for each new message
            await asyncio.sleep(random.uniform(2, 5))
            
            # Limit per run to avoid mass-scraping flags
            if len(messages_to_process) >= 8: break

        print(f"✅ Scraped {len(messages_to_process)} NEW message units.")
        await browser.close()
        return messages_to_process

if __name__ == "__main__":
    messages = asyncio.run(scrape_discord())
    if messages:
        # Save to file for flow_god.py to read
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(messages, f, indent=4)
