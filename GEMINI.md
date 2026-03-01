# FlowGod: Institutional Microstructure Intelligence

FlowGod is a Tier-4 quantitative options flow engine designed to identify aggressive institutional campaigns, model dealer hedging pressure, and predict idiosyncratic alpha through multi-dimensional market analysis.

## 🧠 Core Intelligence Systems

### 1. 3D Exposure Mapping (Vanna/Charm/GEX)
- **GEX 2.0 (Dealer Walls)**: Aggregates Net Gamma across all strikes/expirations to identify **Call Walls** (resistance) and **Put Walls** (support). Includes a **Zero Gamma Flip Point** calculation to detect volatility transition zones.
- **Vanna Slingshots**: Models Delta sensitivity to Volatility. Predicts involuntary dealer buying during IV crushes (e.g., post-earnings or event resolution).
- **Charm Bleeds**: Models Delta sensitivity to Time. Predicts dealer rebalancing as Opex or weekends approach, forcing directional flow regardless of news.

### 2. Recursive Pattern Memory (Self-Learning)
- **Statistical RLHF**: The system "learns" from actual user P&L. When a user saves a trade, a math snapshot (GEX, Vanna, Skew) is captured.
- **Ground Truth Feedback**: `backtester.py` automatically verifies outcomes over a 7-day window. High-profit patterns are tagged as "Golden Setups," while losses are tagged as "Traps."
- **Recursive Weighting**: The scanner dynamically queries this memory to boost the conviction of recurring winning math signatures.

### 3. Market Regime Adaptation
- **Dynamic Regime Sensor**: Uses real-time VIX and SPY price action to categorize the market state (Risk-On, Risk-Off, or High-Volatility Squeeze).
- **Adaptive Weighting**: The scoring engine automatically shifts its bias. In `RISK_OFF`, downside conviction (Puts) is rewarded; in `HIGH_VOLATILITY`, skepticism is increased to avoid "fake out" sweeps.

### 4. Regulatory & Insider Correlation
- **SEC Ghost Filings (Tier-4)**: Real-time integration with the **SEC EDGAR API**. Detects **"Insider Echoes"** (flow mirroring recent Form 4 filings) and **"Stealth Entries"** (unusual flow with no recent disclosures).
- **Congressional Pelosi Signal**: Tracks public House/Senate stock disclosures to flag trades by politicians, triggering high-conviction "Insider" alerts.

### 5. Stealth Ingestion & Discovery
- **Shadow Intelligence**: Bypasses public APIs by shadowing internal JSON endpoints of **Cboe (Block Trades)**, **Stockgrid (Whale Stream)**, and **House Stock Watcher**.
- **Real-Time News Grounding**: Uses the Gemini Google Search tool to find 24-hour idiosyncratic catalysts (Earnings, M&A, Rumors) before issuing a final verdict.
- **Sector Divergence**: Identifies "Idiosyncratic Alpha" by detecting when a stock moves against its sector ETF (Relative Strength/Weakness).

## 🛠 Tech Stack
- **Math Engine**: `NumPy` & `SciPy` (Vectorized Black-Scholes, Greeks, and Microstructure).
- **AI Analyst**: Google Gemini 3 Flash (Real-time news search + quantitative reasoning).
- **Memory**: SQLite-based RAG system with automated schema migrations.
- **Infrastructure**: GitHub Actions (Scanning & Backtesting) + Cloudflare Worker Bridge.

## 📡 Alert Architecture
- **Retail Temperature**: Categorizes social noise into `❄️ Cold (Stealth)`, `🌡️ Lukewarm`, or `🔥 Overheated (Crowded)`.
- **Simplified SEC Signals**: High-signal labels like `🔥 CEO Just Bought` or `🐋 Major Whale Disclosure`.
- **Timing Quality**: Math-backed "Time to Profit" estimates (1-3 Days vs. Hold until Exp).

## 🧪 Validation & Maintenance
- **Testing**: Use `test_suite.py` for full-spectrum validation of math, ingestion, and alerting.
- **CI/CD**: Tests are automatically executed via **GitHub Actions** on manual trigger or workflow dispatch.
- **Redundancy**: Dual-key fallback system for Gemini API to ensure 100% uptime.

## ⚙️ Configurable Thresholds (`config.py`)
- `MIN_STOCK_Z_SCORE`: Threshold for "Ticker Heat" (Default: 2.0).
- `MIN_VOLUME`: Minimum contract volume (Default: 300).
- `MIN_NOTIONAL`: Minimum dollar value (Default: $15,000).
- `MAX_TICKERS`: Watchlist scan limit (Default: 150).
