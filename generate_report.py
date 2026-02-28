import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

prompt = """You are an elite institutional quantitative trader and risk manager. The user has just built 'FlowGod', an institutional-grade options flow scanner with the following Tier-2 capabilities:
- GEX 2.0 (Dealer Walls & Gamma Flips)
- Volatility Surface Mapping (Skew & Term Structure)
- Intraday VWAP & TRV (Sweep Lie Detector)
- Multi-Leg Spread Detection
- Sector Heat Correlation (ETF Baselining)
- RAG-based AI 'Stickiness' verification (overnight OI hold confirmation)

Write a highly detailed, professional report for the user on how to SAFELY profit using this specific intelligence. 

Structure the report as follows:
1. THE EDGE (What this tool actually tells you vs retail scanners)
2. THE PLAYBOOK (Specific, actionable setups to trade using these alerts. Give 3 distinct strategies: e.g., The Gamma Squeeze, The Vol Crush, The Dark Pool Divergence)
3. RISK MANAGEMENT (How to size positions, what invalidates a signal, and the danger of front-running market makers)
4. STATISTICAL REALITY (What are the actual chances of profitability? Be brutally honest about win rates, false positives, and the required mindset of a flow trader).

Keep the tone professional, brutally honest, and deeply technical."""

try:
    response = model.generate_content(prompt)
    with open("report.md", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("Report generated successfully.")
except Exception as e:
    print(f'Error: {e}')
