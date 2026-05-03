#!/bin/bash
# Server-side deploy script — lives at /opt/projects/bowtie-analytics/deploy.sh on the GMK server.
# Not called directly from this repo. Included here as a reference for server bootstrap.
# Run via: ssh gmk './deploy.sh'
set -euo pipefail

PROJECT_DIR="/opt/projects/bowtie-analytics"
LOG_FILE="$PROJECT_DIR/deploy.log"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "[$TIMESTAMP] Deploy started" >> "$LOG_FILE"

cd "$PROJECT_DIR"

echo "[$TIMESTAMP] Pulling new images..." >> "$LOG_FILE"
docker compose pull >> "$LOG_FILE" 2>&1

echo "[$TIMESTAMP] Restarting services..." >> "$LOG_FILE"
docker compose up -d >> "$LOG_FILE" 2>&1

echo "[$TIMESTAMP] Verifying API health..." >> "$LOG_FILE"
for i in 1 2 3 4 5; do
  if curl -fsS http://127.0.0.1:8100/health > /dev/null 2>&1; then
    echo "[$TIMESTAMP] API healthy" >> "$LOG_FILE"
    break
  fi
  sleep 10
done

echo "[$TIMESTAMP] Deploy complete" >> "$LOG_FILE"
