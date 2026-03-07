# FlowGod: Multi-Source AI Options Intelligence

FlowGod is an institutional-grade algorithmic system that monitors high-conviction options flow from **Discord** and **X (Twitter)**. It enriches raw signals with real-time news and SEC filings using **Gemini 3 Flash Preview**, delivering actionable trading signals and daily intelligence reports to Telegram.

## 🚀 Core Features

### 1. Multi-Source Signal Ingestion
- **Discord Monitor:** Scraping of the "Unusual Whales" live feed using Playwright Stealth. 
- **X (Twitter) Intelligence:** A hybrid monitor triggered by Google Apps Script that watches Gmail for @FL0WG0D notifications and uses a "no-login" Playwright scraper.
- **Vision Integration:** Automated OCR of X screenshots via Gemini Vision to decode complex flow tables.

### 2. AI Analysis Engine (Gemini 3 Flash Preview)
- **Contextual Enrichment:** Real-time Google Search integration for ticker-specific news and Form 4 (Insider) SEC filings.
- **Quantitative Filter:** Automatic calculation of RSI, 50-day SMA, and Market-Cap-relative premium thresholds.
- **Institutional Logic:** Identifies "Golden Sweeps," aggressive ask-side filling, and "stacked" repeat flow across different sources.
- **Signal Logic:** Outputs structured JSON with Conviction (1-10), Direction, Leverage, Target Price, and Stop Loss.

### 3. Verification & Performance Layer
- **Market Validator:** Automated post-market script that tracks the real-time price action of every open signal to calculate precise leveraged Win/Loss and ROI.
- **Conviction Calibration Audit:** A weekly self-correction system that analyzes the historical accuracy of AI conviction scores to identify "Alpha Correlation" and model drift.
- **Persistence:** Local SQLite3 database (`flow_god.db`) tracks the full lifecycle of every trade, long-term institutional trends, and end-of-day intelligence reports.

### 4. Automated Operations
- **External Orchestration:** Triggered via **Google Apps Script** (replacing internal GitHub cron) to provide randomized, human-like execution intervals during market hours (9:30 AM - 4:00 PM EST).
- **GitHub Actions Worker:** Responds to repository dispatch events to execute the scraping and AI analysis pipeline.
- **Daily Intelligence Reports:**
    - **Pre-Close Alpha Report:** A comprehensive synthesis of X Analyst intelligence and institutional batch flow (>30 DTE) sent 1 hour before market close (3 PM EST / 20:00 UTC).
- **Session Persistence:** Integrated `session_manager.py` to maintain browser state and bypass Discord/X anti-bot barriers.

## 🛠️ Technical Infrastructure
- **Language:** Python 3.10
- **AI Platform:** Google Gemini (via `google-genai` SDK)
- **Browser Automation:** Playwright (Chromium) + Playwright Stealth
- **Database:** SQLite3 (Local file committed back to repo for state persistence)
- **Messaging:** `python-telegram-bot`
- **Market Data:** `yfinance`

## ⚙️ Setup & Configuration

### GitHub Secrets Required:
| Secret | Description |
| :--- | :--- |
| `GEMINI_API_KEYS` | Comma-separated list of Gemini API keys. |
| `TELEGRAM_TOKEN` | Your Telegram Bot token. |
| `TELEGRAM_CHAT_ID` | Your Telegram User or Channel ID. |
| `DISCORD_SESSION_JSON` | JSON string from `discord_session.json` (generated via `session_manager.py`). |
| `GMAIL_USER` | Gmail address for X notification monitoring. |
| `GMAIL_PASS` | 16-character App Password for Gmail. |

### Development Commands:
- `python discord_scraper.py`: Manually trigger Discord ingestion.
- `python x_monitor.py`: Manually check for new X signals via email.
- `python flow_god.py`: Process ingested messages and dispatch signals.
- `python flow_god.py --report`: Generate the End-of-Day X Intelligence report.
- `python market_validator.py`: Force a manual update of P&L for open signals.
- `python conviction_audit.py`: Run the calibration audit manually.

---
*FlowGod Autopilot v2.5 - Institutional Grade AI Trading Intelligence*
