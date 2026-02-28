import asyncio
import logging
import traceback
import socket
from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

class ErrorReporter:
    """
    Tier-3 Critical Error Reporting System.
    Dispatches system-level failures directly to Telegram.
    """
    
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
        self.chat_id = TELEGRAM_CHAT_ID
        self.hostname = socket.gethostname()

    async def report_critical_error(self, module_name: str, error: Exception, context: str = ""):
        """Sends a high-priority error report to Telegram."""
        if not self.bot or not self.chat_id:
            logging.error(f"Telegram reporting not configured. Error in {module_name}: {error}")
            return

        error_stack = traceback.format_exc()[-500:] # Last 500 chars of stack trace
        
        msg = f"""🔥 CRITICAL SYSTEM FAILURE 🔥
📍 MODULE: {module_name}
🖥️ HOST: {self.hostname}

❌ ERROR: {type(error).__name__}: {str(error)}
📝 CONTEXT: {context}

📂 STACK TRACE (Snippet):
```python
{error_stack}
```
⚠️ IMMEDIATE ACTION REQUIRED."""

        try:
            await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='Markdown')
            logging.info(f"✅ Critical error in {module_name} reported to Telegram.")
        except Exception as e:
            logging.error(f"❌ Failed to send Telegram error report: {e}")

# Global singleton for easy importing
reporter = ErrorReporter()

def notify_error_sync(module_name: str, error: Exception, context: str = ""):
    """Synchronous wrapper for reporting errors in non-async contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(reporter.report_critical_error(module_name, error, context))
        else:
            loop.run_until_complete(reporter.report_critical_error(module_name, error, context))
    except Exception as e:
        logging.error(f"Fallback error reporting failed: {e}")
