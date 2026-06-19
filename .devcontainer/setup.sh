#!/usr/bin/env bash
set -e

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  DevStat — Codespaces Setup                 ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")/.."

# ── Python virtual environment ───────────────────────────────────
echo "[1/4] Creating Python virtual environment..."
python3 -m venv backend/venv
source backend/venv/bin/activate

# ── Python dependencies ──────────────────────────────────────────
echo "[2/4] Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# ── Frontend (pre-built) ─────────────────────────────────────────
echo "[3/4] Frontend is pre-built — skipping npm install & build"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Setup complete!                            ║"
echo "║                                            ║"
echo "║  Run this command to start the server:      ║"
echo "║    bash codespace_setup/start.sh            ║"
echo "║                                            ║"
echo "║  Then open the forwarded port 8150          ║"
echo "║  in your browser.                           ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
