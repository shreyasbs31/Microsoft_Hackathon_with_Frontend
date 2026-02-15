# Honeypot Scam Detection API

## Description

An AI-powered agentic honeypot system that detects scam messages, engages scammers in multi-turn conversations using a dual-layer persona (CBI strategist undercover as a high-value target), extracts actionable intelligence, and reports results to the GUVI evaluation platform.

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI + Uvicorn
- **Database**: SQLite (via SQLAlchemy ORM)
- **LLM (Primary)**: Google Gemini 2.5 Flash (analyst/classification) + Gemini 2.5 Pro (persona/response generation)
- **LLM (Fallback)**: OpenAI GPT-4o-mini (analyst) + GPT-4o (persona)
- **HTTP Client**: httpx (async callbacks)

## Architecture

```
Incoming Message → API Key Validation → Per-Session Lock
    → Normalise Text → Regex Intelligence Extraction
    → Merge Intel with Session → Conditional Translation
    → Conditional Analyst LLM (if NEUTRAL) → Persona LLM Response
    → Update Session DB → Fire Callbacks (at turn 10)
    → Return Reply
```

### Key Components

| Module | Purpose |
|--------|---------|
| `src/main.py` | FastAPI app, request pipeline orchestration |
| `src/models.py` | SQLAlchemy ORM, session state schema |
| `src/analyst.py` | Scam classification LLM (NEUTRAL/HONEYPOT/LEGIT) |
| `src/persona.py` | Dual-layer persona agent with dynamic extraction priorities |
| `src/extractor.py` | Regex-based intelligence extraction (phones, accounts, UPI, URLs, emails, IFSC) |
| `src/translator.py` | Conditional non-English → English translation |
| `src/callback.py` | Final result callback to two GUVI endpoints |
| `src/llm_client.py` | LLM abstraction with Gemini → OpenAI fallback |
| `src/session_lock.py` | Per-session async locks for turn serialisation |
| `src/config.py` | Environment variables and constants |

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/The-Eco-Guy/honey_we_trapped_the_scammers_guvi_finals.git
   cd honey_we_trapped_the_scammers_guvi_finals
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual API keys
   ```

4. **Run the application**
   ```bash
   uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1
   ```

## API Endpoint

- **URL**: `https://your-deployed-url.com/honeypot`
- **Method**: POST
- **Authentication**: `x-api-key` header
- **Health Check**: `GET /health`

### Request Format

```json
{
  "sessionId": "uuid-string",
  "message": {
    "sender": "scammer",
    "text": "Your account has been compromised...",
    "timestamp": 1770005528731
  },
  "conversationHistory": [],
  "metadata": {
    "channel": "SMS",
    "language": "English",
    "locale": "IN"
  }
}
```

### Response Format

```json
{
  "status": "success",
  "reply": "Oh dear, that's concerning. Can you tell me which branch this is from?"
}
```

## Approach

### How We Detect Scams
- **Analyst LLM** (Gemini 2.5 Flash) classifies conversations as NEUTRAL, HONEYPOT, or LEGIT
- Runs conditionally — only when status is NEUTRAL (not yet classified)
- Confidence thresholds: HONEYPOT > 0.5, LEGIT > 0.8
- Regex extraction runs on every turn to capture intelligence from scammer messages

### How We Extract Intelligence
- **Regex patterns** for: phone numbers, bank accounts, UPI IDs, URLs, emails, IFSC codes
- Contextual bank account matching (only near banking keywords)
- UPI ID detection with 30+ known Indian UPI suffixes
- Intelligence accumulates across turns with deduplication

### How We Maintain Engagement
- **Dual-layer persona**: CBI intelligence strategist (hidden) controlling a high-value target persona (visible)
- Dynamic f-string prompts with extraction counts drive conversation strategy
- Priority shifts to fields with 0 extractions, then to fields with lowest counts
- Anti-repetition: last approach summary passed to prompt to prevent repeating tactics
- No hardcoded phases or bait types — fully LLM-driven adaptive behaviour
- Fallback replies if LLM fails, maintaining engagement without breaking

### Concurrency Model
- Multiple sessions handled concurrently (async FastAPI)
- Per-session `asyncio.Lock` ensures turns within a session are processed sequentially
- Single uvicorn worker to ensure lock consistency