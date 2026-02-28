# FlowGod Whale Tracker

FlowGod is a sophisticated institutional-grade options flow scanner and market modeling tool. It identifies aggressive institutional campaigns, dealer hedging pressure, and hidden accumulation using multi-dimensional quantitative models.

## Project Overview

- **Institutional Sweep Detection**: Analyzes execution price relative to the Bid/Ask spread to identify aggressive "Ask-hitting" sweeps (high conviction) vs. passive fills.
- **Sweep Lie Detector (Tier-3)**: Analyzes 1-minute **VWAP divergence** and **Tick-Relative Volume (TRV)** to verify institutional conviction and identify "POC Cleansing" (HVN analysis).
- **Sentiment Fusion (Tier-3)**: Differentiates between institutional alpha and retail FOMO by monitoring real-time **StockTwits Hype Velocity**. Identifies "Quiet Accumulation" vs. "Loud FOMO."
- **GEX 2.0: Institutional Walls**: Aggregates Net GEX across all strikes/expirations to identify **Call Walls** (resistance) and **Put Walls** (support). Flags proximity alerts when price approaches these dealer "pins."
- **Volatility Surface Mapping**: Maps **IV Skew** (25 Delta Put vs Call) and **Term Structure** (Contango/Backwardation) to detect directional institutional bias and event-volatility pricing.
- **Multi-Leg Spread Detection**: Algorithmic leg linkage that identifies **Vertical Spreads** and Straddles, distinguishing structured intent from naked directional bets.
- **Adaptive AI Analyst (RAG Memory)**: Uses a SQLite-based **Retrieval-Augmented Generation** system. The AI (Gemini 3 Flash Preview) remembers historical win-rates for every ticker and trade type.
- **Hybrid Signal Engine**: Combines hard-logic math with Gemini AI validation to provide actionable **Trade Republic** verdicts (BUY, CALL, or PUT).
- **Serverless Trade Verification**: Allows users to save trades via Telegram. A GitHub Action "harvests" these clicks and automatically runs a daily P/L backtester.
- **Stealth Scanning Engine**: Uses a sequential, "Stock-First" approach via a **Cloudflare Worker Bridge** to bypass Yahoo Finance rate limits.

## Core Mandates

- **GitHub Integration**: Every change made to the codebase MUST be committed to GitHub.
- **Documentation Maintenance**: The `GEMINI.md` file must be updated whenever significant changes are implemented.
- **Testing**: Ensure scanning logic and Cloudflare bridge remain functional before committing.

## Tech Stack

- **Live Data**: `yfinance` (Proxied via Cloudflare Worker Bridge)
- **Historical Data**: Massive.com (US) & Alpha Vantage (International)
- **Sentiment Data**: StockTwits (Unauthenticated API)
- **Math Engine**: `scipy` (Black-Scholes, Vanna, Charm, GEX)
- **AI Engine**: Google Gemini 3 Flash Preview (Structured JSON + RAG)
- **Infrastructure**: GitHub Actions & Cloudflare Workers

## Key Thresholds (Configurable in `config.py`)

- `MIN_STOCK_Z_SCORE`: Threshold for "Ticker Heat" (Default: 2.0 std devs)
- `MIN_VOLUME`: Minimum contract volume to consider (Default: 300)
- `MIN_NOTIONAL`: Minimum dollar value of the trade (Default: $15,000)
- `MIN_VOL_OI_RATIO`: Minimum Volume/Open Interest ratio (Default: 6.0x)
- `BASELINE_DAYS`: Number of days for historical baseline (Default: 30)
- `MAX_TICKERS`: Maximum number of tickers scanned per cycle (Default: 150)
