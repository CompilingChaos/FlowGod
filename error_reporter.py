import logging
import os
import traceback
import socket
from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

async def report_critical_error(module_name, error_message):
    """Dispatches system failures directly to Telegram for mobile debugging."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.error(f"Telegram reporter not configured for error: {error_message}")
        return

    hostname = socket.gethostname()
    stack_trace = traceback.format_exc()[-500:] # Get last 500 chars of stack trace
    
    msg = f"""🛑 CRITICAL SYSTEM ERROR 🛑
📍 Module: {module_name}
🖥️ Host: {hostname}

💬 Error: {error_message}

🔍 Trace:
```{stack_trace}```
"""
    
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown')
        logging.info(f"Critical error reported to Telegram from {module_name}")
    except Exception as e:
        logging.error(f"Failed to send error report: {e}")

def log_and_report(module_name):
    """Decorator for async functions to automatically report errors."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await report_critical_error(module_name, str(e))
                raise e
        return wrapper
    return decorator
