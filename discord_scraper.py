import asyncio
import json
import os
import random
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from bs4 import BeautifulSoup
from datetime import datetime

# URL of the Unusual Whales channel provided by the user
DISCORD_URL = "https://discord.com/channels/710524439133028512/1187484002844680354"
SESSION_FILE = "discord_session.json"
MESSAGES_FILE = "unusual_messages.json"

async def scrape_discord():
    # Random jitter: Wait 1 to 5 minutes before starting
    jitter_seconds = random.randint(60, 300)
    print(f"⏳ Humanizing behavior: Sleeping for {jitter_seconds} seconds before scraping...")
    await asyncio.sleep(jitter_seconds)

    if not os.path.exists(SESSION_FILE):
        print(f"❌ Error: {SESSION_FILE} not found. Run 'python session_manager.py' locally first.")
        return []

    async with async_playwright() as p:
        # Launching headless browser for GitHub Actions compatibility
        browser = await p.chromium.launch(headless=True)
        
        # Load saved session state
        context = await browser.new_context(storage_state=SESSION_FILE)
        page = await context.new_page()
        
        # Apply stealth plugins
        await stealth_async(page)
        
        print(f"🚀 Navigating to {DISCORD_URL}...")
        await page.goto(DISCORD_URL)
        
        # Wait for the message container to appear (Discord's DOM uses complex selectors)
        # We wait for the message list to load
        try:
            await page.wait_for_selector('ol[class*="messageListItem"]', timeout=30000)
        except Exception as e:
            print(f"⚠️ Warning: Could not find messages list. Discord might be asking for verification or loading slowly.")
            # Take a screenshot to debug remotely (saved as artifact in GH Actions)
            await page.screenshot(path="debug_discord.png")
            await browser.close()
            return []

        # Wait a bit for all embeds to load
        await asyncio.sleep(5)
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find all message items
        message_items = soup.find_all('ol', class_=lambda x: x and 'messageListItem' in x)
        
        messages_to_process = []
        for item in message_items:
            # Look for the actual message text and embeds
            # Discord's structure is deeply nested. We target the content container.
            msg_content = item.find('div', class_=lambda x: x and 'messageContent' in x)
            embeds = item.find_all('div', class_=lambda x: x and 'embedFull' in x)
            
            text_data = ""
            if msg_content:
                text_data += msg_content.get_text() + "\n"
                
            for embed in embeds:
                # Extract title and description from embeds (Common in bots like Unusual Whales)
                title = embed.find('div', class_=lambda x: x and 'embedTitle' in x)
                desc = embed.find('div', class_=lambda x: x and 'embedDescription' in x)
                if title: text_data += f"TITLE: {title.get_text()}\n"
                if desc: text_data += f"DESC: {desc.get_text()}\n"
            
            if text_data.strip():
                messages_to_process.append({
                    "content": text_data.strip(),
                    "timestamp": datetime.now().isoformat()
                })

        print(f"✅ Scraped {len(messages_to_process)} message units.")
        await browser.close()
        return messages_to_process

if __name__ == "__main__":
    messages = asyncio.run(scrape_discord())
    if messages:
        # Save to file for flow_god.py to read
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(messages, f, indent=4)
