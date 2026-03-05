import asyncio
from playwright.async_api import async_playwright
import os
import glob

def find_opera_path():
    """Use the user-provided exact path for Opera GX."""
    user_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Opera GX', 'opera.exe')
    if os.path.exists(user_path):
        return user_path
        
    # Standard fallback list
    paths = [
        user_path,
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Opera GX', 'launcher.exe'),
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'Opera GX', 'launcher.exe'),
    ]
    
    for path in paths:
        if os.path.exists(path):
            return path
    return None

async def save_session():
    opera_path = find_opera_path()
    
    async with async_playwright() as p:
        # Launching Opera using its executable path
        if opera_path:
            print(f"🌐 Found Opera at: {opera_path}")
            browser = await p.chromium.launch(executable_path=opera_path, headless=False)
        else:
            print("⚠️ Opera not found in standard locations. Launching default Chromium...")
            browser = await p.chromium.launch(headless=False)
            
        context = await browser.new_context()
        page = await context.new_page()
        
        print("\n--- DISCORD SESSION CREATOR (OPERA MODE) ---")
        print("1. Log in to Discord manually in the Opera window.")
        print("2. Navigate to the Unusual Whales channel.")
        print("3. Return here and press ENTER once you are fully logged in.")
        
        await page.goto("https://discord.com/login")
        
        input("\nPress ENTER here once you have finished logging in...")
        
        # Save storage state (cookies, local storage)
        await context.storage_state(path="discord_session.json")
        print("✅ Session saved to 'discord_session.json'.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(save_session())
