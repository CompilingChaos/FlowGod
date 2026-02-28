# FlowGod Whale Tracker

FlowGod is a sophisticated options flow scanner and whale tracking tool, inspired by platforms like Unusual Whales. It identifies institutional-grade trades, unusual volume-to-open-interest ratios, and aggressive "sweep" orders across the US and international equity markets.

## Project Overview

- **Unusual Activity Detection**: Scans for trades where Volume exceeds Open Interest by significant margins or where notional values indicate "whale" activity.
- **Stealth Scanning Engine**: Uses a sequential, "Stock-First" approach to bypass Yahoo Finance rate limits. It performs a light check on stock volume before committing to heavy option chain fetches.
- **Cloudflare Worker Bridge**: All Yahoo Finance requests are proxied through a custom Cloudflare Worker to bypass GitHub Actions IP blocks and ensure 100% uptime.
- **Institutional Ticker Heat**: Integrates Massive.com (US) and Alpha Vantage (International) to calculate official 30-day stock volume baselines.
- **Global Macro Awareness**: Fetches real-time SPY and VIX performance to contextualize whale trades within the broader market sentiment (Risk-On vs. Risk-Off).
- **Hybrid Scoring System**: Uses a point-based scoring mechanism (0-200+) based on:
    - **Ticker Heat**: High Stock Volume Z-Score (>2.0) adds significant weight.
    - **Macro Divergence**: Extra weight if a whale bets against prevailing market fear (e.g., buying calls while VIX is spiking).
    - **Volume & Notional**: High-value trades (>$500k) and high volume (>1000 contracts).
    - **Opening Positions**: Instant flagging if Option Volume > Open Interest.
- **AI-Powered Analysis**: Integrates with Google Gemini 3 Flash. The AI acts as an institutional analyst, identifying "Aggressive Accumulation," "Strategic Hedges," or "Speculative Lotteries."
- **Automated Execution**: Optimized for GitHub Actions. Implements a "Once-per-Day" sync logic to keep historical baselines fresh while keeping trading-hour scans instant.

## Core Mandates

- **GitHub Integration**: Every change made to the codebase MUST be committed to GitHub.
- **Documentation Maintenance**: The `GEMINI.md` file must be updated whenever significant changes, new features, or structural modifications are implemented.
- **Testing**: Before committing, ensure that the scanning logic and alert delivery remain functional.

## Tech Stack

- **Live Data**: `yfinance` (Proxied via Cloudflare Worker Bridge)
- **Historical Data**: Massive.com (US) & Alpha Vantage (International)
- **Language**: Python 3.14+
- **Database**: SQLite (bridged with CSV for GitHub persistence)
- **AI Engine**: Google Gemini 3 Flash
- **Infrastructure**: GitHub Actions & Cloudflare Workers

## Key Thresholds (Configurable in `config.py`)

- `MIN_STOCK_Z_SCORE`: Threshold for "Ticker Heat" (Default: 2.0 std devs)
- `MIN_VOLUME`: Minimum contract volume to consider (Default: 300)
- `MIN_NOTIONAL`: Minimum dollar value of the trade (Default: $15,000)
- `MIN_VOL_OI_RATIO`: Minimum Volume/Open Interest ratio (Default: 6.0x)
- `BASELINE_DAYS`: Number of days for historical baseline (Default: 30)
- `MAX_TICKERS`: Maximum number of tickers scanned per cycle (Default: 150)
