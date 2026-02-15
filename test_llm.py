"""
Diagnostic script — run this to test LLM connectivity.

Usage:
    python test_llm.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai

api_key = os.getenv("GEMINI_API_KEY", "")
print(f"GEMINI_API_KEY present: {bool(api_key)} (len={len(api_key)})")

if not api_key:
    print("ERROR: No GEMINI_API_KEY found in .env")
    sys.exit(1)

genai.configure(api_key=api_key)

# Try listing models first
print("\n=== Available Gemini Models ===")
try:
    models = genai.list_models()
    for m in models:
        if "flash" in m.name.lower() or "pro" in m.name.lower():
            print(f"  {m.name} — {m.display_name}")
except Exception as e:
    print(f"  Error listing models: {e}")

# Try different model names
test_models = [
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.5-pro-preview-05-06",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

print("\n=== Testing Model Names ===")
for model_name in test_models:
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Say hello in one word.")
        print(f"  ✅ {model_name}: {response.text.strip()[:50]}")
    except Exception as e:
        print(f"  ❌ {model_name}: {type(e).__name__}: {str(e)[:150]}")

# Test OpenAI fallback
print("\n=== Testing OpenAI Fallback ===")
openai_key = os.getenv("OPENAI_API_KEY", "")
print(f"OPENAI_API_KEY present: {bool(openai_key)} (len={len(openai_key)})")
if openai_key:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say hello in one word."}],
            timeout=15,
        )
        print(f"  ✅ gpt-4o-mini: {response.choices[0].message.content.strip()[:50]}")
    except Exception as e:
        print(f"  ❌ OpenAI: {type(e).__name__}: {str(e)[:200]}")
else:
    print("  ⚠️  No OpenAI key configured")

print("\nDone.")
