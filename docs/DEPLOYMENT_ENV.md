# Deployment Environment Variables — Bowtie Risk Analytics

**Critical:** The security fixes applied in the April 2026 audit are
code-complete but opt-in via environment variables. Without setting
these correctly at deploy time, several critical security fixes
are NOT activated.

---

## Required at Deployment (Non-Negotiable)

These must be set. Without them the application either won't start
or will run in an insecure state.

| Variable | Required | Description | Example |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | YES | Powers `/explain` endpoint. Without this, RAG evidence narratives fail. | `sk-ant-...` |
| `BOWTIE_API_KEY` | YES (prod) | Activates C-02 API key auth. Without this, all endpoints are unauthenticated. Set to any strong random string. | `your-strong-random-key-here` |
| `BOWTIE_CORS_ORIGINS` | YES (prod) | Activates C-01 CORS restriction. Without this, any origin can call your API. Set to your frontend domain. | `https://yourdomain.com` |

---

## Optional but Recommended

| Variable | Default | Description | Example |
|---|---|---|---|
| `BOWTIE_ENABLE_DOCS` | `false` | Set to `true` only in local dev to enable `/docs` and `/redoc`. Never set true in production. | `false` |
| `OPENAI_API_KEY` | — | Only needed with `--provider openai`. Not required. | `sk-...` |
| `GEMINI_API_KEY` | — | Only needed with `--provider gemini`. Not required. | `AIza...` |

---

## How to Set These

### Local Development (WSL)

Copy the example file and fill in values:

```bash
cp .env.example .env
nano .env
```

Your `.env` should look like:

```env
# Required for /explain endpoint
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Leave these unset in local dev — auth and CORS are open by default
# BOWTIE_API_KEY=
# BOWTIE_CORS_ORIGINS=

# Enable API docs locally
BOWTIE_ENABLE_DOCS=true
```

### Production Server (Docker Compose)

**Never commit `.env` to git.** Pass env vars directly at deploy time:

```bash
# Option 1: .env file on the server (not committed)
cp .env.example .env
# Edit .env on the server with production values

# Then:
docker compose up --build -d
```

Or pass inline:

```bash
ANTHROPIC_API_KEY=sk-ant-... \
BOWTIE_API_KEY=your-strong-random-key \
BOWTIE_CORS_ORIGINS=https://yourdomain.com \
BOWTIE_ENABLE_DOCS=false \
docker compose up --build -d
```

---

## Generating a Strong API Key

Run this on your server to generate `BOWTIE_API_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output. That's your key. Store it somewhere safe.
Anyone who has this key can call your API.

---

## Verify Security Is Active After Deploy

After deploying, run these checks to confirm the security fixes
are actually activated:

```bash
# 1. Confirm auth is enforced (should return 401)
curl -s -o /dev/null -w "%{http_code}" http://localhost/api/health
# Expected: 401 (if BOWTIE_API_KEY is set)

# 2. Confirm auth works with key (should return 200)
curl -s -o /dev/null -w "%{http_code}" \
  -H "X-API-Key: your-strong-random-key" \
  http://localhost/api/health
# Expected: 200

# 3. Confirm docs are disabled (should return 404)
curl -s -o /dev/null -w "%{http_code}" http://localhost/api/docs
# Expected: 404

# 4. Confirm rate limiting is active on /explain
# (send 5 rapid requests — the 4th+ should return 429)
for i in {1..5}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "X-API-Key: your-strong-random-key" \
    -X POST http://localhost/api/explain
done
# Expected: 200 200 429 429 429

# 5. Confirm security headers are present
curl -I -H "X-API-Key: your-strong-random-key" \
  http://localhost/api/health | grep -E "X-Frame|X-Content|Content-Security"
# Expected: headers present
```

---

## What Happens If You Forget

| Missing Variable | Consequence |
|---|---|
| `BOWTIE_API_KEY` not set | All endpoints unauthenticated. Anyone can call `/explain` and run up your Anthropic bill. |
| `BOWTIE_CORS_ORIGINS` not set | Any website can make API calls from a user's browser to your API. |
| `BOWTIE_ENABLE_DOCS=true` in prod | Your full API schema is publicly browsable. |
| `ANTHROPIC_API_KEY` not set | `/explain` endpoint fails with 500 on every call. |

---

## Security Fixes Reference (April 2026 Audit)

These are the fixes that depend on the env vars above:

| Fix ID | What It Does | Activated By |
|---|---|---|
| C-01 | CORS restricted to configured origins | `BOWTIE_CORS_ORIGINS` |
| C-02 | API key authentication | `BOWTIE_API_KEY` |
| C-03 | nginx rate limiting (30r/s general, 2r/s /explain) | Always active — nginx config |
| H-01 | Generic error messages | Always active — code change |
| H-02 | Security headers (CSP, X-Frame-Options, etc.) | Always active — nginx config |
| H-03 | Container runs as non-root | Always active — Dockerfile |
| H-04 | API docs disabled by default | `BOWTIE_ENABLE_DOCS=false` (default) |
| M-01 | Input field length/range validation | Always active — schema change |
| M-02 | Health endpoint info stripped | Always active — code change |
| M-05 | Next.js upgraded (DoS CVE fixed) | Always active — package upgrade |
