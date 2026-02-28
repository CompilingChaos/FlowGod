# FlowGod Whale Tracker

FlowGod is a sophisticated options flow scanner and whale tracking tool, inspired by platforms like Unusual Whales. It identifies institutional-grade trades, unusual volume-to-open-interest ratios, and aggressive "sweep" orders across the US equity markets.

## Project Overview

- **Unusual Activity Detection**: Scans for trades where Volume exceeds Open Interest by significant margins or where notional values indicate "whale" activity.
- **Hybrid Scoring System**: Uses a point-based scoring mechanism (0-200+) based on:
    - **Volume & Notional**: High-value trades (>$500k) and high volume (>1000 contracts).
    - **Relative Volatility**: Z-Score and Relative Volume compared to historical averages.
    - **Market Context**: Implied Volatility (IV), moneyness, and days-to-expiration (DTE).
    - **High-Score Bypass**: Trades with a score ≥ 85 are automatically flagged for AI review even if they miss individual minimum thresholds.
- **AI-Powered Analysis**: Integrates with Google Gemini (1.5 Flash) to provide context-aware reasoning. The AI acts as a final filter, suppressing "routine" trades and identifying high-conviction "sweeps" or "lottery plays".
- **Automated Execution**: Optimized for GitHub Actions to run periodic scans without dedicated infrastructure.
- **Multi-Channel Alerts**: Delivers real-time notifications via Telegram with detailed trade breakdowns and 2-day historical context.
- **Historical Tracking**: Maintains a persistent record of unusual activity in a SQLite/CSV bridge to avoid duplicate alerts and provide long-term context.

## Core Mandates

- **GitHub Integration**: Every change made to the codebase MUST be committed to GitHub.
- **Documentation Maintenance**: The `GEMINI.md` file must be updated whenever significant changes, new features, or structural modifications are implemented.
- **Testing**: Before committing, ensure that the scanning logic and alert delivery remain functional.

## Tech Stack

- **Data Source**: `yfinance` (Yahoo Finance API)
- **Language**: Python 3.14+
- **Database**: SQLite (bridged with CSV for GitHub persistence)
- **AI Engine**: Google Gemini 3 Flash
- **Communication**: Telegram Bot API
- **Workflow**: GitHub Actions

## Key Thresholds (Configurable in `config.py`)

- `MIN_VOLUME`: Minimum contract volume to consider (Default: 300)
- `MIN_NOTIONAL`: Minimum dollar value of the trade (Default: $15,000)
- `MIN_VOL_OI_RATIO`: Minimum Volume/Open Interest ratio (Default: 6.0x)
- `MIN_RELATIVE_VOL`: Minimum volume relative to historical average (Default: 4.0x)
- `MAX_TICKERS`: Maximum number of tickers scanned per cycle (Default: 150)
