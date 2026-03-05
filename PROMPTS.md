# FlowGod: AI Prompt Library

This document preserves the high-intelligence prompts used by FlowGod to analyze "Unusual Whales" flow against market catalysts, technicals, and macro data.

## 1. The High-Intelligence Analysis Engine
**Model:** `gemini-3-flash-preview`
**Mode:** Strict JSON (`application/json`)

### Prompt Structure:
```text
Analyze this Unusual Whales trade report:
{trade_content}

QUANTITATIVE DATA:
{market_data} (Includes RSI, 50/200 SMA, and Macro SPY/QQQ returns)

NEWS & FILINGS:
{news_context} (Includes SEC site search and general news)

HISTORICAL PERFORMANCE:
{stats}

Task:
Provide a CRITICAL analysis. Specifically look for alignment between this trade and the upcoming earnings or recent SEC activity.
- Check for "IV Crush" risk (flag if IV is exceptionally high relative to history).
- Align trade with Macro (SPY/QQQ) and Technicals (RSI/SMAs).

Return a JSON object with exactly these keys:
- is_insider: (boolean)
- insider_conviction: (int 1-10)
- iv_warning: (string or null, e.g. "HIGH IV RISK" or null if safe)
- insider_logic: (Concise explanation of insider evidence, HTML format)
- meaningfulness: (string)
- direction: (LONG/SHORT)
- leverage: (int)
- timeframe_hours: (int)
- target_price: (float)
- stop_loss: (float)
- analysis: (Critical 4-5 sentence analysis in HTML format.)
```

### Key Logic Pillars:
1.  **Macro Alignment:** Filters signals that are "fighting the tape" (e.g., buying calls while SPY/QQQ is crashing).
2.  **Technical Verification:** Checks RSI for overbought/oversold conditions and SMA alignment for trend identification.
3.  **IV Crush Mitigation:** Identifies expensive premiums that might result in losses even if the price move is correct.
4.  **Information Asymmetry:** Prioritizes trades that happen right before Earnings or after specific SEC filings.
