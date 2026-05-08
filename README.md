# Operation Rat-Trap — Agentic Honeypot API

A production-oriented **FastAPI** service that engages suspected scammers in multi-turn dialogue, classifies conversations with an **LLM analyst**, generates believable replies through a **dual-layer persona**, harvests **structured intelligence** (phones, UPI IDs, bank details, URLs, and more) with regex and optional LLM-assisted extraction, and reports outcomes to **GUVI** evaluation callbacks. A **React** dashboard (optional) builds into `static/` and is served by the same application.

For an extended platform and design specification, see **[`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md)**. For publication materials, see the **`paper/`** directory (IEEE LaTeX and figure-generation scripts).

---

## Capabilities

| Area | Description |
|------|-------------|
| **Classification** | Analyst LLM labels each session `NEUTRAL`, `HONEYPOT`, or `LEGIT` when not yet decided; thresholds are configurable. |
| **Persona** | Hidden strategist layer drives a visible “high-value target” persona; prompts adapt to which intelligence fields still need harvest. |
| **Extraction** | Regex and merge logic for Indian UPI/banking patterns, URLs, IFSC, email, and optional LLM extraction pass. |
| **Translation** | Conditional translation to English when metadata or content indicates non-English input. |
| **Concurrency** | Async FastAPI with a **per-session async lock** so turns for one session are serialized. |
| **Callbacks** | At the configured maximum turn, results are POSTed to GUVI callback endpoints (see `src/callback.py`). |

---

## Architecture

High-level request flow (evaluator or custom client):

```text
┌─────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Client    │───▶│  x-api-key check │───▶│  Session lock       │
└─────────────┘    └──────────────────┘    └──────────┬──────────┘
                                                     │
   ┌─────────────────────────────────────────────────┘
   ▼
Normalise text ──► Regex / LLM intel ──► Merge into session
   ▼
Translation (if needed) ──► Analyst (if NEUTRAL) ──► Persona reply
   ▼
Persist session ──► Callbacks at final turn ──► JSON reply
```

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Runtime | Python **3.11+** |
| API | **FastAPI**, **Uvicorn** (single worker recommended for per-session locks) |
| Persistence | **SQLAlchemy 2** — default **`sqlite:///./honeypot.db`**; **PostgreSQL** supported (e.g. Railway) via `DATABASE_URL`; **MySQL** possible via `DATABASE_URL` and `pymysql` |
| Primary LLMs | **Google Gemini** (role-specific model names from environment) |
| Fallback LLMs | **Groq** (e.g. Llama 3.3) when Gemini fails |
| HTTP | **httpx** for async outbound callbacks |
| Dashboard | **React** + **Vite** → static assets under `static/` |

### Source layout

| Path | Role |
|------|------|
| `src/main.py` | FastAPI app, routes, static mount, pipeline orchestration |
| `src/config.py` | Environment-driven configuration |
| `src/models.py` | ORM models and DB session factory |
| `src/analyst.py` | Scam / legitimacy classification |
| `src/persona.py` | Dual-layer persona and reply generation |
| `src/extractor.py` | Intelligence extraction and merging |
| `src/translator.py` | Translation helpers |
| `src/llm_client.py` | Gemini with Groq fallback |
| `src/callback.py` | GUVI and secondary callback delivery |
| `src/session_lock.py` | Per-session `asyncio` locks |
| `frontend/` | React UI; `npm run build` → `../static/` |
| `static/` | Built frontend and assets (served at `/static`, `/`) |
| `render.yaml` / `railway.toml` | Example cloud deployment configuration |

---

## Prerequisites

- Python 3.11 or newer  
- API keys: **Gemini** (required for primary path), **Groq** (recommended for resilience)  
- For the UI: **Node.js 18+** and npm

---

## Quick start

```bash
git clone https://github.com/shreyasbs31/Microsoft_Hackathon_with_Frontend.git
cd Microsoft_Hackathon_with_Frontend

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env — set at least GEMINI_API_KEY and API_KEY
```

Run the API:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Or use the helper script (installs dependencies, then starts Uvicorn):

```bash
chmod +x start.sh
./start.sh
```

- **Interactive docs:** [http://localhost:8000/docs](http://localhost:8000/docs)  
- **Health:** `GET /health` — returns JSON with `status` and timestamp  
- **Root `/`:** serves `static/index.html` when the frontend is built; otherwise redirects to `/docs`

---

## Configuration

Copy `.env.example` to `.env` and set secrets **never committed to git**.

| Variable | Purpose |
|----------|---------|
| `API_KEY` | Shared secret; clients must send header `x-api-key: <value>` on protected routes |
| `GEMINI_API_KEY` | Primary Gemini key; optional `GEMINI_API_KEY_2` … `_5` for rotation |
| `GEMINI_*_MODEL` | Model names for analyst, persona, translator, extractor |
| `GROQ_API_KEY` | Fallback provider |
| `GROQ_*_MODEL` | Groq model names for analyst / persona |
| `DATABASE_URL` | Empty or unset → SQLite file `honeypot.db`; set to Postgres/MySQL URL in production |
| `GUVI_CALLBACK_URL_1`, `GUVI_CALLBACK_URL_2` | Override callback destinations (defaults exist in `config.py`) |
| `MAX_TURNS` | Turn count before callback firing (default `10`) |
| `LLM_TIMEOUT_SECONDS`, `CALLBACK_TIMEOUT_SECONDS` | Network and LLM timeouts |
| `HONEYPOT_CONFIDENCE_THRESHOLD`, `LEGIT_CONFIDENCE_THRESHOLD` | Analyst decision bounds |

See `src/config.py` for defaults and Railway/Postgres URL normalization.

---

## HTTP API

### Authentication

Routes other than the public and frontend prefixes require **`x-api-key`** matching `API_KEY`.

**Public (no API key):** `/`, `/health`, `/docs`, `/redoc`, `/openapi.json`, `/favicon.ico`  
**Frontend / static (no API key):** paths under `/static`, `/api/chat`, `/api/session`…  

**Protected:** `POST /honeypot`, `POST /api/message`, and other non-listed routes.

### Main integration endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/honeypot` | Primary evaluator-shaped payload; returns `{ "status": "success", "reply": "..." }` |
| `POST` | `/api/message` | Alias for `/honeypot` (GUVI platform) |
| `GET` | `/health` | Liveness / health JSON |

### Dashboard helpers (unauthenticated)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Chat-style JSON; returns reply plus session snapshot |
| `GET` | `/api/session/{session_id}` | Current session and extracted intelligence |
| `GET` | `/api/session/{session_id}/results` | Final-style payload when available |

### Example — honeypot request

```json
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "message": {
    "sender": "scammer",
    "text": "Your account will be debited unless you verify now.",
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

```http
POST /honeypot HTTP/1.1
Host: your-host
Content-Type: application/json
x-api-key: your-api-key
```

---

## Frontend (optional)

Build the React app into `static/` so `/` serves the dashboard:

```bash
cd frontend
npm ci
npm run build
```

`vite.config.js` sets `outDir` to `../static` and `base` to `/static/`. In development, `npm run dev` proxies `/api` to `http://localhost:8000`.

---

## Deployment

- **Render:** `render.yaml` defines a Python web service and optional managed database; set `API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, and wire `DATABASE_URL` as in that file.  
- **Railway:** `railway.toml` supplies start command and health check; inject the same secrets and `DATABASE_URL` when using Postgres.

Use **`--workers 1`** in production so per-session locks remain process-local and consistent.

---

## Documentation and research

| Resource | Content |
|----------|---------|
| [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) | Expanded architecture, layers, and design narrative |
| `paper/Operation_RatTrap_IEEE_Paper.tex` | IEEE-formatted manuscript |
| `paper/figures/` | Figures and `generate_figure*.py` scripts |

---

## Security notes

- Treat `API_KEY` as a secret; rotate if leaked.  
- Do not commit `.env` or live database files with real session data.  
- Callback URLs should use HTTPS in production.

---

## Operational notes

- **Single worker:** Multiple Uvicorn workers duplicate in-memory locks; use one worker, or move to a distributed lock if you scale horizontally.  
- **SQLite:** Suitable for development and light loads; use PostgreSQL for concurrent production write load.  
- **Evaluator alignment:** Ensure `API_KEY` matches what the hackathon or staging environment expects.
