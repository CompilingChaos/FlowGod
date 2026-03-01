# FlowGod Whale Tracker

FlowGod is a sophisticated institutional-grade options flow scanner and market modeling tool. It identifies aggressive institutional campaigns, dealer hedging pressure, and hidden accumulation using multi-dimensional quantitative models.

## Project Overview

- **GEX 2.0: Institutional Walls**: Aggregates Net GEX across all strikes/expirations to identify **Call Walls** (resistance) and **Put Walls** (support). Includes a **Zero Gamma Flip Point** calculation to identify volatility transition zones.
- **3D Exposure Mapping (Vanna/Charm)**: Maps **Vanna** (Delta/Vol sensitivity) and **Charm** (Delta/Time decay) to predict involuntary dealer rebalancing ("Vanna Slingshots" and "Charm Bleeds").
- **SEC Ghost Filing Correlation (Tier-4)**: Real-time integration with the **SEC EDGAR API** to detect "Insider Echoes" (flow mirroring recent Form 4/13D filings) and "Stealth Entries" (whale flow with no recent disclosures).
- **Congressional Pelosi Signal (Tier-3)**: Tracks public House/Senate stock disclosures to flag "Insider Trades" by politicians, triggering high-conviction alerts.
- **Adaptive AI Analyst (RAG Memory)**: Uses a SQLite-based **Retrieval-Augmented Generation** system. The AI (Gemini 3 Flash) remembers historical win-rates for every ticker and trade type, grounding alerts in empirical reality.
- **Shadow Intelligence Ingestion**: Bypasses standard APIs by shadowing internal JSON endpoints of **Cboe**, **Stockgrid**, and **House Stock Watcher**.
- **Vectorized Math Engine**: High-performance Greeks and Microstructure calculations using NumPy vectorization, allowing sub-second analysis of full option chains.
- **Tier-3 Critical Error Reporting**: Centralized "Black Box" monitoring that dispatches system failures, API bans, and bridge collapses directly to Telegram with stack traces.

## Core Mandates

- **GitHub Integration**: Every change made to the codebase MUST be committed to GitHub.
- **Documentation Maintenance**: The `GEMINI.md` file must be updated whenever significant changes are implemented.
- **Testing**: Use `test_suite.py` to validate the quant engine, data ingestion, and alerting chain before committing.

## Tech Stack

- **Live Data**: `yfinance` (Proxied via Cloudflare Worker Bridge)
- **Historical/Regulatory Data**: Massive.com, Alpha Vantage, & SEC EDGAR API
- **Math Engine**: `numpy` & `scipy` (Vectorized Black-Scholes, Vanna, Charm, GEX)
- **AI Engine**: Google Gemini 3 Flash (Structured JSON + RAG)
- **Infrastructure**: GitHub Actions & Cloudflare Workers

## Key Thresholds (Configurable in `config.py`)

- `MIN_STOCK_Z_SCORE`: Threshold for "Ticker Heat" (Default: 2.0 std devs)
- `MIN_VOLUME`: Minimum contract volume to consider (Default: 300)
- `MIN_NOTIONAL`: Minimum dollar value of the trade (Default: $15,000)
- `BASELINE_DAYS`: Number of days for historical baseline (Default: 30)
- `MAX_TICKERS`: Maximum number of tickers scanned per cycle (Default: 150)
