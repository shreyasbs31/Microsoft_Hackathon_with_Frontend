#!/usr/bin/env bash
# =============================================================
#  Honeypot API — local start (SQLite by default; see README / .env)
# =============================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Prefer Python 3.11+ (required by this codebase). Honour PYTHON if set and valid.
pick_python() {
    local candidates
    if [[ -n "${PYTHON:-}" ]]; then
        candidates=("$PYTHON")
    else
        candidates=(python3.13 python3.12 python3.11 python3)
    fi
    local c
    for c in "${candidates[@]}"; do
        if command -v "$c" >/dev/null 2>&1 \
            && "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
            command -v "$c"
            return 0
        fi
    done
    return 1
}

if ! PYTHON="$(pick_python)"; then
    echo "ERROR: Python 3.11 or newer is required (found only older python3)."
    echo "Install from https://www.python.org/ or use Homebrew: brew install python@3.11"
    exit 1
fi

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
