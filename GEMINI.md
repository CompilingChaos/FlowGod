# FlowGod: AI-Powered Unusual Whales Signal Analyzer

FlowGod monitors Discord for "Unusual Whales" reports, enriches them with real-time news context via Google Gemini, and delivers high-conviction trading signals (Insider conviction, Leverage, Direction) to Telegram.

## Core Features (Status)
- [x] **Discord Monitor:** Real-time ingestion of Unusual Whales messages from channels.
- [x] **AI Analysis Engine:** Uses Gemini 2.0 Flash to analyze trade flow vs. market sentiment/news.
- [x] **Contextual Enrichment:** Integrated Google Search for news to identify potential insider catalysts.
- [x] **Actionable Signals:** Calculation of trade "meaningfulness," recommended leverage, and direction.
- [x] **Telegram Dispatcher:** Instant delivery of formatted alerts via Telegram bot.
- [x] **GitHub Actions Runner:** Automated execution every 15 minutes with state persistence.
- [ ] **Performance Database:** SQLite integration to track trade entry, recommended action, and leverage.
- [ ] **Market Close Validator:** Daily post-market script to calculate Win/Loss/ROI for historical signals.
- [ ] **AI Feedback Loop:** Dynamic "Strategy Insights" section in Telegram based on historical performance data.

## Infrastructure
- **Language:** Python 3.10
- **AI Platform:** Google Gemini (via `google-genai`)
- **Database:** SQLite3 (Local file committed back to repo)
- **Messaging:** `discord.py`, `python-telegram-bot`
- **Deployment:** GitHub Actions

## Setup Instructions
1.  **Initialize Git:**
    ```powershell
    git init
    git add .
    git commit -m "Initial commit of FlowGod"
    git remote add origin https://github.com/CompilingChaos/FlowGod.git
    git push -u origin main
    ```
2.  **GitHub Secrets:** Set the following secrets in your repository:
    - `GEMINI_API_KEYS`: Comma-separated list (e.g., `key1,key2`).
    - `TELEGRAM_TOKEN`: Your bot token from @BotFather.
    - `TELEGRAM_CHAT_ID`: Your Telegram User/Channel ID.
    - `DISCORD_TOKEN`: Your bot token for Discord.
2.  **Enable Actions:** Ensure GitHub Actions have write permissions to your repository (Settings -> Actions -> General -> Workflow permissions -> Read and write permissions).
