import os
import asyncio
from google import genai

async def validate_keys():
    raw_keys = os.getenv('GEMINI_API_KEYS', '')
    keys = [k.strip() for k in raw_keys.split(',') if k.strip()]
    
    if not keys:
        print("❌ No Gemini API keys found in GEMINI_API_KEYS environment variable.")
        return

    print(f"🔍 Found {len(keys)} keys to test. Starting validation...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    valid_count = 0
    for i, key in enumerate(keys):
        masked_key = f"{key[:4]}...{key[-4:]}"
        try:
            client = genai.Client(api_key=key)
            # Minimal call to check functionality
            response = client.models.generate_content(
                model='gemini-3-flash-preview',
                contents="ping"
            )
            if response.text:
                print(f"✅ Key {i+1} [{masked_key}]: FUNCTIONAL")
                valid_count += 1
            else:
                print(f"⚠️ Key {i+1} [{masked_key}]: NO RESPONSE")
        except Exception as e:
            print(f"❌ Key {i+1} [{masked_key}]: FAILED - {str(e)}")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📊 SUMMARY: {valid_count} of {len(keys)} keys are fully functional.")

if __name__ == "__main__":
    asyncio.run(validate_keys())
