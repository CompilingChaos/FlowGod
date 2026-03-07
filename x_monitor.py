import os
import imaplib
import email
import re
import asyncio
import json
import random
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from flow_god import perform_full_analysis, format_telegram_msg, parse_premium
from database import log_x_signal
from telegram import Bot
from dotenv import load_dotenv
import html
from email.header import decode_header

load_dotenv()

# Config
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_PASS = os.getenv('GMAIL_PASS') # App Password
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

async def get_tweet_alerts_from_email():
    """Check Gmail for new X notifications for targeted accounts."""
    if not GMAIL_USER or not GMAIL_PASS:
        print("❌ Gmail credentials (GMAIL_USER/GMAIL_PASS) missing in environment.")
        return []

    alerts = []
    try:
        # Connect to Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("inbox")

        # Search for any unread email from X
        status, messages = mail.search(None, '(UNSEEN FROM "n-reply@x.com")')
        
        if status != "OK" or not messages[0]:
            mail.logout()
            return []

        # Process notifications
        for num in messages[0].split():
            status, data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            
            # Decode Subject
            subject_bytes, encoding = decode_header(msg.get("Subject", ""))[0]
            if isinstance(subject_bytes, bytes):
                subject = subject_bytes.decode(encoding or 'utf-8', errors='ignore')
            else:
                subject = subject_bytes

            author = None
            if "@FL0WG0D" in subject:
                author = "FLOWGOD"
            elif "NoLimitGains" in subject or "@NoLimitGains" in subject:
                author = "NOLIMITGAINS"
                
            if not author:
                continue

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() in ["text/html", "text/plain"]:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode(errors='ignore')
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode(errors='ignore')

            # Robust URL extraction: handles x.com, twitter.com, and tracking params
            url_pattern = r'https?://(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/\d+'
            url_match = re.search(url_pattern, html.unescape(body))
            
            if url_match:
                final_url = url_match.group(0)
                alerts.append({"url": final_url, "author": author})
                mail.store(num, '+FLAGS', '\\Seen')

        mail.logout()
    except Exception as e:
        print(f"⚠️ Gmail Error: {e}")
        
    return alerts

async def scrape_tweet_no_login(url):
    """Visit the tweet URL without login and extract text/images."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        
        print(f"🚀 Navigating to: {url}")
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5)
            
            tweet_text = ""
            text_el = await page.query_selector('div[data-testid="tweetText"]')
            if text_el:
                tweet_text = await text_el.inner_text()

            image_urls = []
            img_els = await page.query_selector_all('div[data-testid="tweetPhoto"] img')
            for img in img_els:
                src = await img.get_attribute('src')
                if src and "card_img" not in src:
                    image_urls.append(src)

            await browser.close()
            return tweet_text, image_urls
        except Exception as e:
            print(f"⚠️ Playwright Error: {e}")
            await browser.close()
            return None, None

async def main():
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN missing.")
        return

    alerts = await get_tweet_alerts_from_email()
    if not alerts:
        print("📭 No new targeted email alerts.")
        return

    bot = Bot(token=TELEGRAM_TOKEN)

    for alert in alerts:
        url = alert['url']
        author = alert['author']
        print(f"🔔 Found Alert from {author}: {url}")

        if author == "NOLIMITGAINS":
            # Just send the link directly to Telegram
            msg = f"🚨 <b>NoLimitGains Posted:</b>\n{url}"
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='HTML')
            print("✅ NoLimitGains link dispatched.")
            continue

        if author == "FLOWGOD":
            text, images = await scrape_tweet_no_login(url)
            
            if not text and not images:
                print("⚠️ Could not extract tweet content.")
                continue

            # Extract ticker and premium for logging
            ticker_match = re.search(r'\b([A-Z]{2,5})\b', text) if text else None
            ticker = ticker_match.group(1).upper() if ticker_match else "SCAN"
            prem_match = re.search(r'Prem(?:ium)?:\s*\$([\d\.,]+[KMB]?)', text, re.I) if text else None
            premium = parse_premium(prem_match.group(1) if prem_match else "0")
            is_sweep = "SWEEP" in (text.upper() if text else "")

            # Always log for the daily report
            log_x_signal(ticker, text if text else "[IMAGE ONLY]", is_sweep, premium)

            # Perform full analysis for high-conviction immediate alert
            data, ticker, stats, entry_price, stable_id = await perform_full_analysis(text if text else "", images=images)
            
            if data and data not in ["STORED", "FILTERED_BY_CAP"]:
                if isinstance(data, dict) and data.get('insider_conviction', 0) >= 6:
                    msg = format_telegram_msg(ticker, data, stats)
                    msg = msg.replace("FLOWGOD:", "FLOWGOD [X]:")
                    # Append the X Link
                    msg += f"\n🔗 <a href='{url}'>View Post on X</a>"
                    
                    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='HTML', disable_web_page_preview=True)
                    print(f"✅ X Signal Dispatched: {ticker}")
            else:
                print(f"⏭️ Signal filtered or stored: {ticker if ticker else 'Unknown'}")

if __name__ == "__main__":
    asyncio.run(main())
