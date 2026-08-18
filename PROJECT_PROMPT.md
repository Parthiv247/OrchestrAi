# OrchestrAI — Full Project Prompt (Master Context)

Use this prompt at the start of any new chat session to give Claude full context of the project.

---

## What Is This Project?

**OrchestrAI** is an Autonomous Multi-Agent AI Platform for Self-Healing Data Pipelines — an MTech final semester capstone project by Parthiv Patel. The goal is to have this as a live, portfolio-grade project that can be shown to data/AI companies for job applications.

The project was initially vibe-coded (UI-first, fake data). The current effort is to make it a **real, working product** — real Postgres, real Groq NL-to-SQL, real ML anomaly detection, real dbt transformations, and a live deployed URL.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| Backend | FastAPI (Python 3.11), SQLAlchemy, Alembic migrations |
| AI/LLM | Groq API (llama-3.3-70b-versatile) for NL-to-SQL, cost optimization, diagnosis |
| Agents | LangGraph (StateGraph) multi-agent pipeline |
| Database | PostgreSQL 15 (Docker container: `orchestrai-postgres`, port 5432) |
| Vector Store | ChromaDB 0.5.23 (Docker container: `orchestrai-chromadb`, port 8001) |
| ML | scikit-learn: IsolationForest (anomaly detection) + RandomForestClassifier (healing strategy) |
| Data Transform | dbt-core 1.8.0 + dbt-postgres 1.8.0 |
| Auth | JWT (python-jose), bcrypt password hashing |
| Realtime | WebSocket (FastAPI native) |
| Workflow | Apache Airflow 2.9.1 (in docker-compose, optional) |
| Deployment | Docker Compose (local), Railway.toml (backend), Vercel (frontend) |

---

## Project Location

- **Root:** `/Users/parthivpatel/OrchetraAI/`
- **Backend:** `/Users/parthivpatel/OrchetraAI/backend/`
- **Frontend:** `/Users/parthivpatel/OrchetraAI/frontend/`
- **ML Models:** `/Users/parthivpatel/OrchetraAI/ml/`
- **dbt Project:** `/Users/parthivpatel/OrchetraAI/dbt_project/`
- **Migrations:** `/Users/parthivpatel/OrchetraAI/backend/migrations/`

---

## API Keys & Secrets (Already Configured)

```
GROQ_API_KEY=gsk_<rotate this — get new key from console.groq.com>
GROQ_MODEL=llama-3.3-70b-versatile
POSTGRES_HOST=localhost (or "postgres" inside Docker)
POSTGRES_PORT=5432
POSTGRES_DB=orchestrai
POSTGRES_USER=admin
POSTGRES_PASSWORD=orchestrai_secret
CHROMA_HOST=localhost (or "chromadb" inside Docker)
CHROMA_PORT=8001
JWT_SECRET_KEY=<generate: python3 -c "import secrets; print(secrets.token_hex(32))">
```

Env files: `.env` (root), `backend/.env`, `frontend/.env.local`

---

## Architecture — How It Works

```
User types NL question
        ↓
  Query Agent (Groq NL→SQL)
        ↓
  Validation Agent (check SQL safety)
        ↓
  Execute on PostgreSQL
        ↓
  Results → Frontend chart/table

Separately, background loop:
  Monitoring Agent (IsolationForest anomaly detection)
        ↓ anomaly detected
  Diagnosis Agent (Groq root-cause analysis)
        ↓
  HITL Approval (human approves/rejects on /approvals page)
        ↓ approved
  Healing Agent (applies fix: restart, rollback, reindex, scale)
        ↓
  Learning Agent (updates healing_outcomes table, improves strategy)
```

The 10 LangGraph agents:
1. **QueryAgent** — NL-to-SQL via Groq
2. **ValidationAgent** — blocks dangerous SQL
3. **MonitoringAgent** — IsolationForest anomaly detection
4. **DiagnosisAgent** — Groq root-cause analysis
5. **HealingAgent** — applies the fix
6. **LearningAgent** — records outcomes, updates strategy
7. **CostOptimizerAgent** — rewrites expensive queries via Groq
8. **DeploymentAgent** — stub (deployment orchestration)
9. **LineageAgent** — dbt manifest parsing for column lineage
10. **AlertAgent** — Slack webhook notifications

---

## Backend — Key Files

```
backend/
├── main.py                    # FastAPI app, lifespan (migrations + seed + ML train)
├── core/
│   ├── config.py              # Settings from env vars
│   ├── db.py                  # SQLAlchemy engine + connection pool
│   ├── seed_demo.py           # Seeds 500 orders + 80 pipeline_runs on first boot
│   └── seed_outcomes.py       # Seeds 45 healing_outcomes rows
├── agents/
│   ├── orchestrator.py        # LangGraph StateGraph — the healing loop
│   ├── query_agent.py         # NL-to-SQL (Groq)
│   ├── monitoring_agent.py    # IsolationForest anomaly detection
│   ├── diagnosis_agent.py     # Groq diagnosis
│   ├── healing_agent.py       # Fix applier
│   ├── learning_agent.py      # healing_outcomes MTTR tracker
│   └── cost_optimizer.py      # Groq query rewriter
├── routers/
│   ├── analytics.py           # /api/analytics — NL-to-SQL queries
│   ├── pipelines.py           # /api/pipelines — CRUD + runs
│   ├── incidents.py           # /api/incidents — anomaly incidents
│   ├── approvals.py           # /api/approvals — HITL approve/reject
│   ├── connectors.py          # /api/connectors — connector catalog
│   ├── quality.py             # /api/quality — schema registry, drift
│   ├── settings.py            # /api/settings — team, tokens, audit
│   ├── auth.py                # /api/auth — login, register, JWT
│   ├── lineage.py             # /api/lineage — dbt manifest lineage
│   ├── optimizer.py           # /api/optimizer — cost optimization
│   ├── observability.py       # /api/observability — metrics
│   ├── notifications.py       # /api/notifications — Slack alerts
│   └── reports.py             # /api/reports — scheduled reports
├── db/
│   └── models.py              # SQLAlchemy ORM models (all tables)
├── migrations/
│   ├── env.py                 # Reads DB from env vars (not hardcoded)
│   └── versions/              # Alembic migration files
└── startup.sh                 # Docker startup: alembic → dbt → uvicorn
```

---

## Frontend — Key Pages

```
frontend/src/app/
├── page.tsx                   # Dashboard (redirect to /overview)
├── overview/page.tsx          # Main dashboard — metrics, pipeline status, activity feed
├── analyst/page.tsx           # AI Analyst — NL-to-SQL chat interface
├── pipelines/
│   ├── page.tsx               # Pipeline list
│   ├── new/page.tsx           # Pipeline builder (multi-step)
│   └── [id]/page.tsx          # Pipeline detail + run history
├── approvals/page.tsx         # HITL approval queue (WebSocket real-time)
├── connectors/page.tsx        # Connector catalog + My Connections
├── lineage/page.tsx           # Data lineage graph (dbt manifest)
├── quality/page.tsx           # Schema registry, drift detection, rules
├── observability/page.tsx     # System metrics, SLA tracker, ML metrics
├── optimizer/page.tsx         # Query cost optimizer
├── dbt/page.tsx               # dbt run status and models
├── reports/page.tsx           # Scheduled reports + email digest
├── settings/page.tsx          # Team, tokens, notifications, audit log
├── onboarding/page.tsx        # 5-step onboarding wizard
└── login/page.tsx             # JWT auth login

frontend/src/lib/
├── api.ts                     # Centralized fetch wrapper (all API calls go through here)
├── queries.ts                 # React Query hooks
└── utils.ts                   # Helpers
```

---

## Database Tables (PostgreSQL)

```sql
-- Auth
users                  -- id, email, password_hash, role, workspace_id

-- Pipeline tracking
pipelines              -- id, name, source, destination, schedule, status
pipeline_runs          -- id, pipeline_id, status, records_loaded, records_failed, duration_seconds, started_at, log

-- Self-healing
incidents              -- id, pipeline_id, anomaly_type, severity, status, detected_at
healing_outcomes       -- id, incident_id, strategy, mttr_seconds, success, created_at

-- AI Analyst
query_history          -- id, user_id, question, sql, result_count, created_at

-- Connectors
connector_configs      -- id, name, type, credentials_encrypted, status

-- Data Quality
schema_registry        -- id, table_name, columns_json, version, created_at
quality_rules          -- id, rule_name, rule_sql, severity, enabled

-- Settings
api_tokens             -- id, user_id, name, token_hash, created_at
audit_log              -- id, user_id, action, resource, created_at

-- Raw data (seeded)
raw.ecommerce_orders   -- 500 real e-commerce orders (seed data)
```

---

## ML Models

Location: `ml/`
- `isolation_forest.pkl` — trained on pipeline_runs data for anomaly detection
- `healing_classifier.pkl` — RandomForestClassifier for strategy selection
- `train_models.py` — trains both models; reads real pipeline_runs from DB first, falls back to synthetic

Auto-training: if `.pkl` files are missing at startup, `main.py` calls `train_models.py` automatically.

---

## dbt Project

Location: `dbt_project/`
- Reads from `raw.ecommerce_orders`
- Creates `staging.stg_orders` (cleaned)
- Creates `marts.fct_orders` (aggregated facts)
- `profiles.yml` reads DB connection from env vars
- Runs inside Docker backend startup via `startup.sh`

---

## Docker Setup

```yaml
# docker-compose.yml services:
postgres:    port 5432 (host) ← PostgreSQL database
chromadb:    port 8001 (host) ← Vector store
backend:     port 8000 (host) ← FastAPI (Dockerfile.backend)
frontend:    port 3000 (host) ← Next.js (Dockerfile.frontend, container port 3001)
airflow-*:   port 8080 (host) ← Airflow (optional, heavy)
```

**To start everything:**
```bash
cd /Users/parthivpatel/OrchetraAI
docker-compose up -d postgres chromadb backend
cd frontend && npm run dev   # starts on port 3000
```

Or double-click `START_ORCHESTRAI.command` in the OrchetraAI folder.

**Backend startup sequence** (handled by `backend/startup.sh`):
1. Wait for PostgreSQL to be ready
2. `alembic upgrade head` — run migrations
3. `dbt run` — build staging/mart tables
4. `uvicorn backend.main:app` — start API server
5. On first boot: seed 500 orders + 80 pipeline_runs + 45 healing_outcomes

---

## Deployment Config

- `railway.toml` — Railway.app backend deployment (Dockerfile.backend)
- `render.yaml` — Render.com alternative
- `DEPLOY.md` — Step-by-step deployment guide

For production:
- Backend → Railway (connects to Railway Postgres addon)
- Frontend → Vercel (set `NEXT_PUBLIC_API_URL` to Railway backend URL)

---

## What Is Actually Real vs Fake (Honest Assessment)

### Real and Working:
- Groq NL-to-SQL via `query_agent.py` — actually calls Groq API, returns real SQL
- PostgreSQL schema + Alembic migrations — real tables, not mocked
- Seed data — 500 real ecommerce orders, 80 pipeline_runs
- JWT auth — real bcrypt + JWT tokens
- dbt transformations — real SQL models
- IsolationForest anomaly detection — trained on real pipeline_runs
- WebSocket for real-time approvals
- HITL approval flow (approve/reject incidents)
- Cost optimizer — real Groq rewrite of SQL queries

### Partially Real / Needs Work:
- The healing actions (restart, rollback, reindex) are partially stubbed — they log the action but don't actually restart a real Docker container
- Airflow integration — configured but not tested end-to-end
- Snowflake destination — reads env vars but falls back to local PG schema
- Email notifications — stub (logs only, no real SMTP wired)

### What Makes It Portfolio-Grade (Still Needed):
1. **Live URL** — not deployed yet, still localhost only
2. **Real demo data flow** — need to show a pipeline failing and healing in real-time
3. **End-to-end smoke test** — no single command that proves everything works
4. **UI polish** — currently good but could use Tremor data components

---

## Key Issues Fixed (History)

- Fixed `next dev --port 3001` → now uses port 3000
- Fixed `docker-compose` frontend port mapping `3001:3001` → `3000:3001`
- Updated Groq API key (new key in `.env` and `backend/.env`)
- Fixed `alembic env.py` to read DB host from env vars (not hardcoded localhost)
- Added `backend/startup.sh` — runs alembic + dbt + uvicorn in sequence
- Added `backend/core/seed_demo.py` — seeds real data on first boot
- Fixed ML training to use real pipeline_runs from DB
- Fixed 10+ security issues (SQL injection, magic token backdoor, CORS)
- Fixed WebSocket cross-event-loop crash
- Fixed 79+ pytest suite passing

---

## Benchmarks (Measured, from Experiments)

These were run in a controlled sandbox, not on real external pipelines:
- MTTR: OrchestrAI 4.2 min vs manual baseline 18.7 min (78% improvement claimed)
- NL-to-SQL accuracy: 67% on Spider v1.0 subset (target was >65%) ✅
- Query cost reduction: 34% average (target was >30%) ✅

Note: The MTTR benchmark was run on injected synthetic failures, not production failures.

---

## Pending Work

1. **Get localhost:3000 working** — Docker backend + frontend npm dev
2. **Deploy to Railway + Vercel** — get a live URL
3. **Make healing loop actually work end-to-end** — inject a real failure, watch it heal
4. **Replace UI with Tremor components** — much better data dashboard look
5. **Write a proper README** with screenshots and live URL
6. **Record a 2-minute demo video** for the portfolio

---

## For New Chat Session — Start Here

Tell Claude:
> "I am continuing OrchestrAI from `/Users/parthivpatel/OrchetraAI/`. Read PROJECT_PROMPT.md for full context. My goal is [specific task]. Start immediately."

The project has been through 219 tracked tasks across multiple sessions. All code is in the OrchetraAI folder. Don't re-explain what was done — just continue from where we are.
