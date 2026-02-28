# FlowGod Whale Tracker

FlowGod is a sophisticated institutional-grade options flow scanner and market modeling tool. It identifies aggressive institutional campaigns, dealer hedging pressure, and hidden accumulation using multi-dimensional quantitative models.

## Project Overview

- **GEX 2.0: Institutional Walls**: Aggregates Net GEX across all strikes/expirations to identify **Call Walls** (resistance) and **Put Walls** (support). Flags proximity alerts when price approaches these dealer "pins."
- **Volatility Surface Mapping**: Maps **IV Skew** (25 Delta Put vs Call) and **Term Structure** (Contango/Backwardation) to detect directional institutional bias and event-volatility pricing.
- **Multi-Leg Spread Detection**: Algorithmic leg linkage that identifies **Vertical Spreads** and Straddles, distinguishing structured intent from naked directional bets.
- **Adaptive AI Analyst (RAG Memory)**: Uses a SQLite-based **Retrieval-Augmented Generation** system. The AI (Gemini 3 Flash) remembers historical win-rates for every ticker and trade type.
- **Dark Pool Proxy Detection**: Infers hidden institutional absorption by monitoring intraday **Volume/Price Compression** (Dark Z-Score).
- **Sweep Lie Detector**: Analyzes 1-minute **VWAP divergence** and **Tick-Relative Volume (TRV)** to verify institutional conviction.
- **Stickiness Reputation System**: Verifies if whales held positions overnight by tracking opening OI changes (Vector 5 logic).

## Core Mandates

- **GitHub Integration**: Every change made to the codebase MUST be committed to GitHub.
- **Documentation Maintenance**: The `GEMINI.md` file must be updated whenever significant changes are implemented.
- **Testing**: Ensure scanning logic and Cloudflare bridge remain functional before committing.

## Tech Stack

- **Live Data**: `yfinance` (Proxied via Cloudflare Worker Bridge)
- **Historical Data**: Massive.com (US) & Alpha Vantage (International)
- **Math Engine**: `scipy` (Black-Scholes, Vanna, Charm, GEX)
- **AI Engine**: Google Gemini 3 Flash (Structured JSON + RAG)
- **Database**: SQLite (bridged with CSV for GitHub persistence)
- **Infrastructure**: GitHub Actions & Cloudflare Workers

## Key Thresholds (Configurable in `config.py`)

- `MIN_STOCK_Z_SCORE`: Threshold for "Ticker Heat" (Default: 2.0 std devs)
- `MIN_VOLUME`: Minimum contract volume to consider (Default: 300)
- `MIN_NOTIONAL`: Minimum dollar value of the trade (Default: $15,000)
- `BASELINE_DAYS`: Number of days for historical baseline (Default: 30)
- `MAX_TICKERS`: Maximum number of tickers scanned per cycle (Default: 150)
