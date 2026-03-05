# FlowGod: AI Prompt Library

This document preserves the high-intelligence prompts used by FlowGod to analyze "Unusual Whales" flow against market catalysts, technicals, macro data, and advanced option metrics.

## 1. The Institutional-Grade Analysis Engine
**Model:** `gemini-3-flash-preview`
**Mode:** Strict JSON (`application/json`)

### Prompt Structure:
```text
Analyze this Unusual Whales trade report:
{trade_content}

QUANTITATIVE & OPTION DATA:
{market_data} (Includes RSI, 50SMA, Macro trends, Market Cap, ADV, and Volume vs Open Interest)

NEWS & FILINGS:
{news_context}

HISTORICAL PERFORMANCE:
{stats}

Task:
Provide a CRITICAL analysis. Specifically look for alignment between this trade and the upcoming earnings or recent SEC activity.
- Identify if this is a "GOLDEN SWEEP" (Volume > Open Interest).
- Evaluate trade size significance relative to Market Cap and Average Daily Volume (ADV).
- Check for "IV Crush" risk and technical alignment.

Return a JSON object with exactly these keys:
- is_insider: (boolean)
- insider_conviction: (int 1-10)
- is_golden_sweep: (boolean, true if trade Volume > existing Open Interest)
- iv_warning: (string or null)
- insider_logic: (Concise explanation of insider evidence, HTML format)
- meaningfulness: (string, explanation of trade size vs mkt cap/vol)
- direction: (LONG/SHORT)
- leverage: (int)
- timeframe_hours: (int)
- target_price: (float)
- stop_loss: (float)
- analysis: (Critical 4-5 sentence analysis in HTML format.)
```

### Key Logic Pillars:
1.  **Golden Sweep Identification:** Prioritizes trades where the volume exceeds existing Open Interest, indicating a massive *new* institutional bet.
2.  **Market Cap Scaling:** Calibrates the "Meaningfulness" of a trade based on the company's size (e.g., $1M in Small Cap > $1M in Megacap).
3.  **Macro & Technical Filtering:** Prevents chasing pumps into overbought conditions or fighting a bearish market tide.
4.  **IV Risk Management:** Flags expensive premiums to protect against the post-catalyst volatility crush.
