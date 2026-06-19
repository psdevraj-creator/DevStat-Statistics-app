#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."
source backend/venv/bin/activate

echo "Starting DevStat server..."
cd backend
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8150
