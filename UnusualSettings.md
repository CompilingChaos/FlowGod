# Unusual Whales: Exact "FlowGod" Configuration Blueprint

This document provides the **precise, non-vague** settings for the Unusual Whales Premium Discord Bot. Use this as a step-by-step implementation guide to achieve the highest signal-to-noise ratio for your FlowGod AI engine.

---

## 1. Primary Setup: The `/configure` Menu
Run the `/configure` slash command. An ephemeral menu titled **"Automatic Post Configuration"** will appear.

### A. Live Options Flow (The "Whale" Feed)
1.  **Select Topic Dropdown:** Choose `Live Options Flow`.
2.  **Select Channel Dropdown:** Choose `#🏆-golden-sweeps`.
3.  **Action:** Click the **"Change Parameters"** button that appears below the status text.
4.  **Sub-Menu Settings (The Exact Filters):**
    *   **Premium Min:** Select or type `500,000`.
    *   **Vol > OI:** Click to set to `ENABLED` (This is the most critical insider filter).
    *   **Order Type:** Select `Sweeps Only`.
    *   **Side:** Select `Ask`.
    *   **Equity Type:** Deselect `ETFs` and `Indices` (Focus only on `Stocks`).
    *   **Moneyness:** Select `Out of the Money`.
    *   **DTE:** Set range to `0 - 45 days`.
5.  **Save:** Click **"Apply"** or the checkmark icon.

### B. Insider Trades (The "Evidence" Feed)
1.  **Select Topic Dropdown:** Choose `Insider Trades`.
2.  **Select Channel Dropdown:** Choose `#🕵️-insider-activity`.
3.  **Action:** Click the **"XYZ (Watchlist)"** button.
4.  **Filter Logic:** Ensure the **"Watchlist Only"** toggle is `DISABLED` (so you see all sector whales) UNLESS you only trade specific names.
5.  **Minimum Value:** Set to `$100,000`.

---

## 2. Professional Watchlist: The `XYZ` Menu
In the same `/configure` menu, click the **"XYZ (Watchlist)"** button to manage your priority tickers.

### The "Elite 10" Watchlist (Recommended)
Add these tickers for 5-minute interval "Urgent Volume" alerts:
`NVDA, TSLA, AAPL, MSFT, AMD, PLTR, MSTR, META, AMZN, GOOGL`

*   **Update Frequency:** Select `5 Minutes`.
*   **Topic:** Enable `Ticker Updates`.
*   **Attributes:** Enable `Unusual Volume` and `Put/Call Ratio Shift`.

---

## 3. High-Conviction "Golden" Presets
If the bot offers a **"Presets"** dropdown in the "Change Parameters" menu, use these exact combinations:

| Preset Name | Target Goal |
| :--- | :--- |
| **Golden Sweeps** | High-urgency new institutional positions. |
| **Whale Trades** | Extreme premium ($1M+) detection. |
| **Bullish Flow** | Aggressive call buying above the ask. |

---

## 4. Visual Implementation Checklist
Ensure your Discord channels match this exact logic:

| Channel Name | Filter Key | Exact Setting |
| :--- | :--- | :--- |
| `#🏆-golden-sweeps` | `Vol > OI` | **ON** |
| `#🏆-golden-sweeps` | `Premium` | **>$500,000** |
| `#🏆-golden-sweeps` | `Type` | **Sweeps Only** |
| `#🕵️-insider-activity` | `Topic` | **Insider Trades (SEC Form 4)** |
| `#🕵️-insider-activity` | `Value` | **>$100,000** |

---

## 5. Deployment Confirmation
Once configured, your channels should only post 5–15 alerts per market day. If you receive more than 30 alerts, increase the **Premium Min** to `$1,000,000` to further refine the quality.
