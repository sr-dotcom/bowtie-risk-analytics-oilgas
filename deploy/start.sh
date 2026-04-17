#!/bin/bash
set -euo pipefail

# Start FastAPI backend
cd /app
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 &
FASTAPI_PID=$!

# Start Next.js standalone frontend
cd /app/frontend
node server.js &
NEXTJS_PID=$!

# Give services a moment to bind before nginx starts accepting traffic
sleep 3

# Start nginx (foreground — keeps container alive)
nginx -g "daemon off;"
