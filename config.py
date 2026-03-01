import os
import logging

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_KEY_FALLBACK = os.getenv("GEMINI_API_KEY_FALLBACK")
MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
CLOUDFLARE_PROXY_URL = os.getenv("CLOUDFLARE_PROXY_URL")

WATCHLIST_FILE = "watchlist.csv"
DB_FILE = "database.db"
ERROR_LOG = "errors.log"

# Configure Logging: Output to console for GitHub Actions logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Silence secondary libraries
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("requests").setLevel(logging.ERROR)

# --- Thresholds ---
MIN_VOLUME = 300
MIN_NOTIONAL = 15000
MIN_VOL_OI_RATIO = 6.0
MIN_RELATIVE_VOL = 4.0
MAX_TICKERS = 150 

# --- Stock-Level Baselines (Massive.com) ---
MIN_STOCK_Z_SCORE = 2.0  # Alert if volume is > 2 std devs from mean
BASELINE_DAYS = 30
# ------------------
