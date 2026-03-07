#!/bin/bash
# =============================================================
#  Honeypot Scam Detection API — Local Startup Script
# =============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

MYSQL_BIN="/opt/homebrew/opt/mysql/bin/mysql"
MYSQLD_SAFE="/opt/homebrew/opt/mysql/bin/mysqld_safe"
MYSQL_DATADIR="/opt/homebrew/var/mysql"
PYTHON="/usr/local/bin/python3"
HOST="${APP_HOST:-0.0.0.0}"
PORT="${APP_PORT:-8000}"

echo ""
echo "============================================"
echo "  Honeypot Scam Detection API"
echo "  Local Deployment"
echo "============================================"
echo ""

# ---- 1. Check MySQL ----
echo "[1/4] Checking MySQL..."
if ! pgrep -x mysqld > /dev/null 2>&1; then
    echo "  MySQL not running. Starting..."
    "$MYSQLD_SAFE" --datadir="$MYSQL_DATADIR" &
    sleep 3
    if pgrep -x mysqld > /dev/null 2>&1; then
        echo "  MySQL started successfully."
    else
        echo "  ERROR: Could not start MySQL. Start it manually:"
        echo "    $MYSQLD_SAFE --datadir=$MYSQL_DATADIR &"
        exit 1
    fi
else
    echo "  MySQL is already running."
fi

# ---- 2. Create database if needed ----
echo "[2/4] Ensuring database exists..."
"$MYSQL_BIN" -u root -e "CREATE DATABASE IF NOT EXISTS honeypot_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>/dev/null
echo "  Database 'honeypot_db' ready."

# ---- 3. Install Python deps ----
echo "[3/4] Checking Python dependencies..."
"$PYTHON" -m pip install -q -r requirements.txt 2>/dev/null
echo "  Dependencies installed."

# ---- 4. Start the API server ----
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "localhost")
echo "[4/4] Starting Honeypot API server..."
echo ""
echo "============================================"
echo "  API Endpoints:"
echo "  Local:    http://localhost:$PORT"
echo "  Network:  http://$LOCAL_IP:$PORT"
echo "  Health:   http://localhost:$PORT/health"
echo "  Docs:     http://localhost:$PORT/docs"
echo "============================================"
echo ""

"$PYTHON" -m uvicorn src.main:app --host "$HOST" --port "$PORT" --workers 1
