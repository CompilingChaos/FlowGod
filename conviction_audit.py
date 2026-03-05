import sqlite3
import asyncio
from datetime import datetime
from telegram import Bot
import os
from dotenv import load_dotenv

load_dotenv()
DB_NAME = 'flow_god.db'
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def get_calibration_stats():
    """Analyze win rates and ROI per conviction score bucket."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Only analyze CLOSED trades
        cursor.execute("SELECT conviction_score, is_win, pnl FROM trades WHERE status = 'CLOSED'")
        trades = cursor.fetchall()
        
        if not trades:
            return None

        buckets = {
            "Elite (9-10)": {"wins": 0, "total": 0, "pnl": []},
            "High (7-8)": {"wins": 0, "total": 0, "pnl": []},
            "Mid (5-6)": {"wins": 0, "total": 0, "pnl": []},
            "Speculative (1-4)": {"wins": 0, "total": 0, "pnl": []}
        }

        for t in trades:
            score = t['conviction_score']
            win = t['is_win']
            pnl = t['pnl']
            
            if score >= 9: b = "Elite (9-10)"
            elif score >= 7: b = "High (7-8)"
            elif score >= 5: b = "Mid (5-6)"
            else: b = "Speculative (1-4)"
            
            buckets[b]["total"] += 1
            buckets[b]["wins"] += win
            buckets[b]["pnl"].append(pnl)

        results = []
        for name, data in buckets.items():
            if data["total"] > 0:
                win_rate = (data["wins"] / data["total"]) * 100
                avg_roi = sum(data["pnl"]) / data["total"]
                results.append({
                    "name": name,
                    "win_rate": win_rate,
                    "avg_roi": avg_roi,
                    "total": data["total"]
                })
        
        return results

async def send_audit_report():
    stats = get_calibration_stats()
    if not stats:
        print("No data for audit yet.")
        return

    msg = "⚖️ <b>CONVICTION CALIBRATION AUDIT</b>\n"
    msg += f"<i>Generated: {datetime.now().strftime('%Y-%m-%d')}</i>\n"
    msg += "━━━━━━━━━━━━━━━━━\n"
    
    total_alpha = 0
    for s in stats:
        msg += f"<b>{s['name']}:</b>\n"
        msg += f"WR: {s['win_rate']:.1f}% | Avg ROI: {s['avg_roi']:+.1f}% ({s['total']} signals)\n\n"
        if "Elite" in s['name'] or "High" in s['name']:
            total_alpha += s['avg_roi']

    msg += "━━━━━━━━━━━━━━━━━\n"
    if total_alpha > 0:
        msg += "✅ <b>VERDICT:</b> Model shows positive alpha correlation. High conviction scores are valid."
    else:
        msg += "⚠️ <b>VERDICT:</b> Calibration mismatch detected. High conviction signals are underperforming."

    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='HTML')
    print("✅ Audit report sent to Telegram.")

if __name__ == "__main__":
    asyncio.run(send_audit_report())
