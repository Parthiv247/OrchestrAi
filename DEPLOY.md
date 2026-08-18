# OrchestrAI — Deployment Guide

## Architecture

```
Internet → Vercel (Next.js frontend)
                ↓ API calls
           Railway (FastAPI backend)
                ↓
         Railway PostgreSQL + ChromaDB
```

---

## Step 1 — Get a Groq API Key

1. Go to https://console.groq.com
2. Create account → API Keys → Create new key
3. Copy the key — you'll need it in Step 3

---

## Step 2 — Push code to GitHub

```bash
cd /path/to/OrchetraAI

# Make sure .env is NOT tracked
git rm --cached .env 2>/dev/null || true
git rm --cached backend/.env 2>/dev/null || true

# Commit everything (ml/ pkl files are now included)
git add .
git commit -m "feat: production deployment setup"
git push origin main
```

---

## Step 3 — Deploy Backend on Railway

1. Go to https://railway.app → New Project → Deploy from GitHub
2. Select your `OrchetraAI` repo
3. Railway auto-detects `railway.toml` → uses `Dockerfile.backend`
4. Add a **PostgreSQL** plugin: click + → Database → PostgreSQL
5. Set these environment variables in the Railway dashboard:

```
GROQ_API_KEY         = gsk_...your new key...
GROQ_MODEL           = llama-3.3-70b-versatile
APP_ENV              = development
JWT_SECRET_KEY       = (generate: openssl rand -hex 32)
ENCRYPTION_KEY       = (generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
POSTGRES_HOST        = (from Railway PostgreSQL plugin — copy the host)
POSTGRES_PORT        = 5432
POSTGRES_DB          = railway
POSTGRES_USER        = postgres
POSTGRES_PASSWORD    = (from Railway PostgreSQL plugin)
CORS_ORIGINS         = https://your-app.vercel.app  ← fill in after Step 4
```

6. Click Deploy. Wait for health check to pass at `/health`.
7. Copy your Railway URL: `https://orchestrai-backend-xxxx.up.railway.app`

---

## Step 4 — Deploy Frontend on Vercel

1. Go to https://vercel.com → New Project → Import from GitHub
2. Select `OrchetraAI` repo → set **Root Directory** to `frontend`
3. Add environment variable:
   ```
   NEXT_PUBLIC_API_URL = https://orchestrai-backend-xxxx.up.railway.app
   ```
4. Click Deploy
5. Copy your Vercel URL: `https://orchestrai-xxxx.vercel.app`

---

## Step 5 — Wire them together

1. Go back to Railway → backend service → environment variables
2. Update `CORS_ORIGINS` = `https://orchestrai-xxxx.vercel.app`
3. Redeploy backend

---

## Step 6 — Verify everything works

Visit your Vercel URL. Check:
- [ ] Dashboard loads with data
- [ ] AI Analyst: type "show revenue by category" → returns chart
- [ ] Pipelines: 3 demo pipelines visible
- [ ] ML Health panel shows model metrics
- [ ] `/health` endpoint: `{"postgres": "ok"}`

---

## Local Development (Docker)

```bash
# Start all services
docker-compose up -d

# Check health
curl http://localhost:8000/health

# Frontend
cd frontend && npm install && npm run dev
# → open http://localhost:3000
```

---

## ChromaDB on Railway (Optional)

The backend degrades gracefully if ChromaDB is unavailable (RAG features disabled).
To add it: Railway → New Service → Docker Image → `chromadb/chroma:0.5.23`
Then set `CHROMA_HOST` and `CHROMA_PORT` in backend env vars.
