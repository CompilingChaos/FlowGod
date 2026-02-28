import logging
import os
import pandas as pd
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_TOKEN

# File to store saved trades
TRADES_FILE = "trades_to_verify.csv"

# Ensure CSV exists with header
if not os.path.exists(TRADES_FILE):
    pd.DataFrame(columns=["contract", "ticker", "entry_price", "date", "p_l", "status"]).to_csv(TRADES_FILE, index=False)

async def handle_save_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data # format: save_CONTRACT_PRICE
    if data.startswith("save_"):
        try:
            parts = data.split("_")
            contract = parts[1]
            entry_price = float(parts[2])
            ticker = contract[:4] # Approximation, backtester will refine
            
            # Save to CSV
            df = pd.read_csv(TRADES_FILE)
            if contract not in df['contract'].values:
                new_row = {
                    "contract": contract,
                    "ticker": ticker,
                    "entry_price": entry_price,
                    "date": datetime.now().isoformat(),
                    "p_l": 0.0,
                    "status": "OPEN"
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_csv(TRADES_FILE, index=False)
                
                await query.edit_message_caption(caption=f"{query.message.text}

✅ SAVED TO VERIFICATION LOG")
                # If it's a regular message, we edit the text
                await query.edit_message_text(text=f"{query.message.text}

✅ SAVED TO VERIFICATION LOG")
            else:
                await query.answer(text="Trade already saved.", show_alert=True)
        except Exception as e:
            logging.error(f"Save button failed: {e}")

if __name__ == "__main__":
    logging.info("Starting Telegram Listener for 'Save Trade' button...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CallbackQueryHandler(handle_save_button))
    app.run_polling()
