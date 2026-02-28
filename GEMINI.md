# FlowGod Whale Tracker

FlowGod is a sophisticated options flow scanner and whale tracking tool, inspired by platforms like Unusual Whales. It identifies institutional-grade trades, unusual volume-to-open-interest ratios, and aggressive "sweep" orders across the US equity markets.

## Project Overview

- **Unusual Activity Detection**: Scans for trades where Volume exceeds Open Interest by significant margins or where notional values indicate "whale" activity.
- **Institutional Ticker Heat**: Integrates Massive.com (formerly Polygon.io) to calculate official 30-day stock volume baselines. This identifies where "Smart Money" is crowding the underlying stock before looking at options.
- **Hybrid Scoring System**: Uses a point-based scoring mechanism (0-200+) based on:
    - **Ticker Heat**: High Stock Volume Z-Score (>2.0) adds significant weight to signals.
    - **Volume & Notional**: High-value trades (>$500k) and high volume (>1000 contracts).
    - **Relative Volatility**: Z-Score and Relative Volume compared to historical averages.
    - **Opening Positions**: Instant flagging if Option Volume > Open Interest for a specific contract.
- **AI-Powered Analysis**: Integrates with Google Gemini 3 Flash to provide context-aware reasoning. The AI filters out routine trades and identifies high-conviction "sweeps" or "lottery plays" based on ticker heat and option flow.
- **Automated Execution**: Optimized for GitHub Actions. Runs `massive_sync.py` to refresh baselines (respecting the 5 req/min limit) before performing the live scan.
- **Historical Tracking**: Maintains a persistent record of unusual activity in a SQLite/CSV bridge to avoid duplicate alerts and provide long-term context.

## Core Mandates

- **GitHub Integration**: Every change made to the codebase MUST be committed to GitHub.
- **Documentation Maintenance**: The `GEMINI.md` file must be updated whenever significant changes, new features, or structural modifications are implemented.
- **Testing**: Before committing, ensure that the scanning logic and alert delivery remain functional.

## Tech Stack

- **Data Source**: `yfinance` (Yahoo Finance API)
- **Historical Data**: Massive.com (US) & Alpha Vantage (International)
- **Language**: Python 3.14+
- **Database**: SQLite (bridged with CSV for GitHub persistence)
- **AI Engine**: Google Gemini 3 Flash
- **Communication**: Telegram Bot API
- **Workflow**: GitHub Actions

## Key Thresholds (Configurable in `config.py`)

- `MIN_STOCK_Z_SCORE`: Threshold for "Ticker Heat" (Default: 2.0 std devs)
- `MIN_VOLUME`: Minimum contract volume to consider (Default: 300)
- `MIN_NOTIONAL`: Minimum dollar value of the trade (Default: $15,000)
- `MIN_VOL_OI_RATIO`: Minimum Volume/Open Interest ratio (Default: 6.0x)
- `BASELINE_DAYS`: Number of days for Massive.com baseline (Default: 30)
- `MAX_TICKERS`: Maximum number of tickers scanned per cycle (Default: 150)
