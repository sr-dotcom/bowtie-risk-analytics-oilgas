# ============================================================
# Stage 1: Build Next.js frontend (standalone output)
# ============================================================
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
# Default API URL: in the combined container nginx proxies /api/ to FastAPI
# running on localhost:8000, so Next.js rewrites are not exercised for
# browser-initiated fetches. This value is only needed for SSR paths.
ENV NEXT_PUBLIC_API_URL=http://localhost:8000
RUN npm run build

# ============================================================
# Stage 2: Production image — Python API + Node frontend + nginx
# ============================================================
FROM python:3.12-slim AS production

WORKDIR /app

# System packages: nginx for reverse proxy, curl for healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

# Install Node.js (needed to run Next.js standalone server.js)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy Python backend
COPY src/ ./src/
COPY configs/ ./configs/
COPY scripts/association_mining/ ./scripts/association_mining/

# Copy model artifacts (baked into image from local build machine)
COPY data/models/artifacts/ ./data/models/artifacts/
COPY data/evaluation/rag_workspace/ ./data/evaluation/rag_workspace/
COPY data/evaluation/apriori_rules.json ./data/evaluation/apriori_rules.json

# Copy built Next.js standalone output
COPY --from=frontend-build /app/frontend/.next/standalone /app/frontend/
COPY --from=frontend-build /app/frontend/.next/static /app/frontend/.next/static
COPY --from=frontend-build /app/frontend/public /app/frontend/public

# Nginx single-container config
COPY deploy/nginx.conf /etc/nginx/sites-available/default

# Startup script
COPY deploy/start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
  CMD curl -sf http://localhost:8080/api/health || exit 1

CMD ["/app/start.sh"]
