import asyncio
import logging
import os
from alerts import send_alert
from scanner import generate_system_verdict

# Setup minimal logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(message)s')

async def run_test_scenario():
    print("🚀 Starte FlowGod Test-Szenario: NVDA Institutional Campaign...")

    # 1. Das hypothetische Trade-Objekt (NVDA Sweep)
    test_trade = {
        'ticker': 'NVDA',
        'contract': 'NVDA240621C00150000',
        'type': 'CALLS',
        'strike': 150.0,
        'exp': '2024-06-21',
        'volume': 8500,
        'oi': 1200,
        'premium': 5.20,
        'notional': 4420000,
        'rel_vol': 15.2,
        'z_score': 6.8,
        'stock_z': 4.2,
        'delta': 0.48,
        'gamma': 0.025,
        'vanna': 0.12,
        'charm': 0.05,
        'gex': 1250000,
        'call_wall': 160.0,
        'put_wall': 130.0,
        'flip': 142.0,
        'skew': -0.04,
        'bias': 'BULLISH',
        'score': 165,
        'aggression': 'Aggressive (Ask) | Institutional Sweep (TRV Max)',
        'sector': 'AI & Semiconductors',
        'bid': 5.10,
        'ask': 5.20,
        'underlying_price': 138.50,
        'detection_reason': 'Vol > OI (Opening Position), Near Gamma Flip, TRV Max Aggression'
    }

    # 2. Der Markt-Kontext (Bullish / Risk-On)
    test_macro = {
        'spy': 0.65,
        'vix': -3.2,
        'dxy': -0.4,
        'tnx': -1.2,
        'qqq': 0.95,
        'sentiment': 'Bullish / Risk-On | Liquidity Expansion'
    }

    # 3. Teste den System-Verdict (Hard Logic)
    verdict, logic = generate_system_verdict(test_trade)
    print(f"✅ System-Check abgeschlossen. Vorschlag: {verdict}")
    print(f"   Logik: {logic}")

    # 4. Sende den Alert (Triggered Gemini AI für die Validierung)
    print("\n🧠 Kontaktiere Gemini AI für das finale Hybrid-Verdict...")
    
    ticker_context = "Historical Note: NVDA whales have shown 80% stickiness in the last 30 days."
    
    sent = await send_alert(test_trade, ticker_context, test_macro)

    if sent:
        print("\n✨ ERFOLG: Die Telegram-Nachricht wurde gesendet!")
        print("Überprüfe jetzt dein Smartphone für das FlowGod Verdict.")
    else:
        print("\n❌ FEHLER: Nachricht konnte nicht gesendet werden. Prüfe deine API-Keys.")

if __name__ == "__main__":
    asyncio.run(run_test_scenario())
