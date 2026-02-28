# FlowGod Whale Tracker

FlowGod is a sophisticated options flow scanner and whale tracking tool, inspired by platforms like Unusual Whales. It identifies institutional-grade trades, unusual volume-to-open-interest ratios, and aggressive "sweep" orders across the US and international equity markets.

## Project Overview

- **Unusual Activity Detection**: Scans for trades where Volume exceeds Open Interest by significant margins or where notional values indicate "whale" activity.
- **Sweep Lie Detector (Vector 1)**: Analyzes 1-minute intraday stock price action and **VWAP divergence** to verify if an options whale was truly aggressive or just a passive block trade.
- **GEX & Greeks Engine (Vector 2)**: Locally calculates Delta, Gamma, and Gamma Exposure (GEX) using the Black-Scholes model to identify potential "Gamma Squeezes" and dealer hedging pressure.
- **Advanced Correlation Engine (Vector 3)**: Identifies institutional campaigns by clustering trades by Ticker and Sector. Uses ETF baselining to distinguish true sector divergence from broad market moves.
- **Institutional AI Analyst (Vector 4)**: Integrates Gemini 3 Flash with a strict logic-driven rubric. Uses global macro context (SPY, VIX, DXY, TNX) to identify contrarian "Smart Money" bets.
- **Stickiness Reputation System (Vector 5)**: Systematically verifies if yesterday's whales held their positions by tracking overnight Open Interest changes. Automatically adjusts "Ticker Trust Scores."
- **Stealth Scanning Engine**: Uses a sequential, "Stock-First" approach via a **Cloudflare Worker Bridge** to bypass Yahoo Finance rate limits and GitHub IP blocks.

## Core Mandates

- **GitHub Integration**: Every change made to the codebase MUST be committed to GitHub.
- **Documentation Maintenance**: The `GEMINI.md` file must be updated whenever significant changes, new features, or structural modifications are implemented.
- **Testing**: Before committing, ensure that the scanning logic and alert delivery remain functional.

## Tech Stack

- **Live Data**: `yfinance` (Proxied via Cloudflare Worker Bridge)
- **Historical Data**: Massive.com (US) & Alpha Vantage (International)
- **Language**: Python 3.14+
- **Math Engine**: `scipy` (Black-Scholes & Statistics)
- **AI Engine**: Google Gemini 3 Flash (Structured JSON)
- **Infrastructure**: GitHub Actions & Cloudflare Workers

## Key Thresholds (Configurable in `config.py`)

- `MIN_STOCK_Z_SCORE`: Threshold for "Ticker Heat" (Default: 2.0 std devs)
- `MIN_VOLUME`: Minimum contract volume to consider (Default: 300)
- `MIN_NOTIONAL`: Minimum dollar value of the trade (Default: $15,000)
- `MIN_VOL_OI_RATIO`: Minimum Volume/Open Interest ratio (Default: 6.0x)
- `BASELINE_DAYS`: Number of days for historical baseline (Default: 30)
- `MAX_TICKERS`: Maximum number of tickers scanned per cycle (Default: 150)
