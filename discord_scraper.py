import asyncio
import json
import os
import random
from playwright.async_api import async_playwright
import playwright_stealth
from bs4 import BeautifulSoup
from datetime import datetime

# URL of the Unusual Whales channel provided by the user
DISCORD_URL = "https://discord.com/channels/710524439133028512/1187484002844680354"
SESSION_FILE = "discord_session.json"
MESSAGES_FILE = "unusual_messages.json"

async def scrape_discord():
    # Random jitter: Wait 1 to 5 minutes before starting
    # jitter_seconds = random.randint(60, 300)
    # print(f"⏳ Humanizing behavior: Sleeping for {jitter_seconds} seconds before scraping...")
    # await asyncio.sleep(jitter_seconds)

    if not os.path.exists(SESSION_FILE):

        print(f"❌ Error: {SESSION_FILE} not found. Run 'python session_manager.py' locally first.")
        return []

    async with async_playwright() as p:
        # Launching headless browser for GitHub Actions compatibility
        browser = await p.chromium.launch(headless=True)
        
        # Load saved session state
        context = await browser.new_context(storage_state=SESSION_FILE)
        page = await context.new_page()
        
        # Apply stealth plugins (Definitive Fix for 'module object is not callable')
        try:
            import playwright_stealth
            # 1. Try calling it as a function directly from the package
            if callable(playwright_stealth.stealth):
                playwright_stealth.stealth(page)
            # 2. Try calling the function inside the submodule if the names collided
            elif hasattr(playwright_stealth.stealth, 'stealth') and callable(playwright_stealth.stealth.stealth):
                playwright_stealth.stealth.stealth(page)
            else:
                print("⚠️ Warning: Found stealth module/attribute but none are callable.")
        except Exception as e:
            print(f"⚠️ Warning: Stealth application failed. {e}")
        
        print(f"🚀 Navigating to {DISCORD_URL}...")
        await page.goto(DISCORD_URL)
        
        # Extra wait for the page to stabilize
        await page.wait_for_load_state("networkidle")
        
        print(f"👀 Page title: {await page.title()}")
        
        # Wait for the message container to appear
        try:
            # We look for ANY message list item (Discord's class name for messages often starts with "message_")
            await page.wait_for_selector('li[class*="messageListItem"], ol[class*="messageListItem"]', timeout=45000)
        except Exception as e:
            print(f"⚠️ Warning: Could not find messages list. Taking debug screenshot...")
            # Take a screenshot to debug remotely (saved as artifact in GH Actions)
            await page.screenshot(path="debug_discord.png")
            
            # Check for "Login" or "Verify" to help debugging
            content = await page.content()
            if "Login" in content: print("❌ Detected 'Login' page. Session might be expired.")
            elif "Verify you are human" in content: print("❌ Detected 'hCaptcha/Verification' page.")
            
            await browser.close()
            return []

        # Wait a bit for all embeds to load
        await asyncio.sleep(5)
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find all message items using broader selectors
        # Discord uses li[class*="messageListItem"] or div[role="listitem"]
        message_items = soup.find_all(['li', 'div'], class_=lambda x: x and 'messageListItem' in x)
        if not message_items:
            # Fallback: look for any element that looks like a message container
            message_items = soup.find_all('li', id=lambda x: x and x.startswith('chat-messages-'))

        messages_to_process = []
        # Process the last few items found
        for item in message_items[-15:]: 
            if len(messages_to_process) >= 3:
                break
            
            # --- BRUTE FORCE TEXT EXTRACTION ---
            # Instead of looking for specific containers, we grab all text
            # inside the list item that isn't UI junk (like "Reply" buttons)
            raw_text = item.get_text(separator=" ").strip()
            
            # Filter out common UI noise
            noise = ["(edited)", "NEW", "Reply", "Pins", "Threads"]
            for n in noise: raw_text = raw_text.replace(n, "")
            
            if len(raw_text) > 10: # Ignore empty/tiny items
                messages_to_process.append({
                    "content": raw_text.strip(),
                    "timestamp": datetime.now().isoformat()
                })

        print(f"✅ Scraped {len(messages_to_process)} message units via Brute Force.")

        if not messages_to_process and message_items:
            print(f"⚠️ Found {len(message_items)} potential items but failed to extract text. Check DOM structure.")
        await browser.close()
        return messages_to_process

if __name__ == "__main__":
    messages = asyncio.run(scrape_discord())
    if messages:
        # Save to file for flow_god.py to read
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(messages, f, indent=4)
