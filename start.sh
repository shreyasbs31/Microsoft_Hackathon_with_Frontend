#!/usr/bin/env bash
# =============================================================
#  Honeypot API — local start (SQLite by default; see README / .env)
# =============================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

PYTHON="${PYTHON:-$(command -v python3)}"
HOST="${APP_HOST:-0.0.0.0}"
PORT="${APP_PORT:-8000}"

echo ""
echo "============================================"
echo "  Honeypot Scam Detection API"
echo "============================================"
echo ""

echo "[1/2] Installing dependencies (quiet)..."
"$PYTHON" -m pip install -q -r requirements.txt

LOCAL_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
[[ -z "$LOCAL_IP" ]] && LOCAL_IP="localhost"

echo "[2/2] Starting server — http://localhost:$PORT  (docs: /docs)"
echo "      Network:  http://${LOCAL_IP}:$PORT"
echo ""

exec "$PYTHON" -m uvicorn src.main:app --host "$HOST" --port "$PORT" --workers 1
