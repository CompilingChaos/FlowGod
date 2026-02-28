import os
import logging

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

WATCHLIST_FILE = "watchlist.csv"
DB_FILE = "database.db"
ERROR_LOG = "errors.log"

# Configure Logging: Only ERROR and above goes to the file.
logging.basicConfig(
    level=logging.INFO, # Global level
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ERROR_LOG),
        logging.StreamHandler() # Still print to console for GitHub Action logs
    ]
)

# Silence secondary libraries
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

# To fulfill the "silent if all goes well" requirement, we'll set the 
# FileHandler to ONLY record Errors.
file_logger = logging.FileHandler(ERROR_LOG)
file_logger.setLevel(logging.ERROR)
logging.getLogger().addHandler(file_logger)

# Constants
MIN_VOLUME = 500
MIN_NOTIONAL = 25000
MIN_VOL_OI_RATIO = 8.0
MIN_RELATIVE_VOL = 5.0
MAX_TICKERS = 50 
