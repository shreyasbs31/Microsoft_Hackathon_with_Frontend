"""
Configuration module — loads environment variables and defines constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- API Authentication ---
API_KEY = os.getenv("API_KEY", "default-dev-key")

# --- LLM Provider Keys ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# --- Gemini Model Names ---
GEMINI_ANALYST_MODEL = os.getenv("GEMINI_ANALYST_MODEL", "gemini-2.5-flash")
GEMINI_PERSONA_MODEL = os.getenv("GEMINI_PERSONA_MODEL", "gemini-2.5-flash")
GEMINI_TRANSLATOR_MODEL = os.getenv("GEMINI_TRANSLATOR_MODEL", "gemini-2.5-flash")
GEMINI_EXTRACTOR_MODEL = os.getenv("GEMINI_EXTRACTOR_MODEL", "gemini-2.0-flash")

# --- Groq Fallback Model Names ---
GROQ_ANALYST_MODEL = os.getenv("GROQ_ANALYST_MODEL", "llama-3.3-70b-versatile")
GROQ_PERSONA_MODEL = os.getenv("GROQ_PERSONA_MODEL", "llama-3.3-70b-versatile")

# --- Callback URLs ---
GUVI_CALLBACK_URL_1 = os.getenv(
    "GUVI_CALLBACK_URL_1",
    "https://hackathon.guvi.in/api/updateHoneyPotFinalResult",
)
GUVI_CALLBACK_URL_2 = os.getenv(
    "GUVI_CALLBACK_URL_2",
    "https://guvi-platform.com/api/intelligence/callback",
)

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://honeypot_user:password@localhost:5432/honeypot_db")

# --- Timeouts ---
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "15"))
CALLBACK_TIMEOUT_SECONDS = int(os.getenv("CALLBACK_TIMEOUT_SECONDS", "5"))

# --- Conversation ---
MAX_TURNS = int(os.getenv("MAX_TURNS", "10"))

# --- Engagement Duration ---
# Evaluator scores: >0s=1pt, >60s=2pts, >180s=1pt. At 10 turns, 20s/turn = 200s > 180s.
ESTIMATED_SECONDS_PER_TURN = int(os.getenv("ESTIMATED_SECONDS_PER_TURN", "20"))

# --- Classification Thresholds ---
HONEYPOT_CONFIDENCE_THRESHOLD = float(os.getenv("HONEYPOT_CONFIDENCE_THRESHOLD", "0.5"))
LEGIT_CONFIDENCE_THRESHOLD = float(os.getenv("LEGIT_CONFIDENCE_THRESHOLD", "0.8"))

# --- Fallback Replies (when both LLMs fail) ---
FALLBACK_REPLIES = [
    "I see, let me think about this for a moment...",
    "Sorry, I was busy. Can you repeat that?",
    "Hmm, I'm a bit confused. Can you explain again?",
    "Oh okay, hold on let me check my account first.",
    "Actually wait, I need to find my details. One second.",
    "I'm not sure I understand. What should I do exactly?",
    "Let me just verify something on my end quickly...",
    "Oh dear, this is worrying. What do you need from me?",
]
