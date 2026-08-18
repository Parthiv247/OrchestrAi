# OrchestrAI — Live Demo Script
## MTech Final Viva Demo Guide

---

## 🚀 ONE-COMMAND STARTUP

Open Terminal in the OrchestrAI folder and run:

```bash
./start_demo.sh
```

This automatically:
1. Starts Docker (postgres + chromadb)
2. Seeds 10,000 real e-commerce orders + 2,000 customers into PostgreSQL
3. Starts FastAPI backend on **http://localhost:8000**
4. Registers PostgreSQL→Snowflake connectors and creates 4 pipelines
5. Starts Next.js frontend on **http://localhost:3001**
6. Opens the browser

**If anything fails:** Check logs with `tail -f /tmp/orchestrai_backend.log`

---

## 📋 DEMO FLOW (12 minutes)

### 1. Dashboard Overview (2 min)
**URL:** http://localhost:3001/

> *"OrchestrAI monitors all data pipelines in real time. Here we see 4 active pipelines syncing our e-commerce PostgreSQL data to Snowflake."*

- Point to the **Pipeline Health** cards (success rate, records loaded)
- Point to the **AI Agents panel** — 10 agents working
- Show the **live sync indicator** in the TopBar (green, pulsing)
- Show the **Activity Feed** with recent pipeline events

---

### 2. Connector Gallery (1 min)
**URL:** http://localhost:3001/connectors

> *"OrchestrAI connects to 17+ data sources out of the box. Let me show the active connections."*

- Click **My Connections** tab → shows PostgreSQL Source + Snowflake Destination
- Show the connector catalog: Databases, Cloud Warehouses, APIs, Files

---

### 3. Pipeline Monitoring (2 min)
**URL:** http://localhost:3001/pipelines

> *"Here are our 4 active pipelines moving e-commerce data from PostgreSQL to Snowflake."*

- Show the pipeline list with status badges and record counts
- Click **"E-Commerce Orders → Snowflake"** pipeline
- Show: 90-day run history, success/failure chart, records/sec graph
- **Say:** *"Each pipeline run is automatically tracked. Failed runs trigger the self-healing agents."*

---

### 4. AI Analyst — Natural Language Queries (3 min) ⭐ KEY DEMO
**URL:** http://localhost:3001/analyst

> *"This is the AI Analyst — powered by Groq's llama-3.3-70b. You ask questions in plain English, it generates and runs SQL automatically."*

**Run these queries in order** (copy-paste or type):

1. `Show total revenue by region for the last 12 months`
   → Bar chart appears: North America dominates, Europe second

2. `Which product categories have the highest profit margin?`
   → Services > Software > Hardware table with margins

3. `Top 10 customers by total spend`
   → Leaderboard table — Enterprise segment customers dominate

4. `Monthly revenue trend with month-over-month growth rate`
   → Time series chart showing growth trajectory

5. `Which sales rep has the highest win rate and total revenue?`
   → Per-rep breakdown table

> *"The system converts natural language to SQL using our Query Agent, validates it with the Validation Agent, and streams results. This is what makes OrchestrAI different — no SQL knowledge needed."*

---

### 5. Self-Healing Demo (2 min) ⭐ KEY DEMO
**URL:** http://localhost:3001/approvals

> *"Now the star feature — autonomous self-healing. When a pipeline fails, the AI detects the anomaly, diagnoses the root cause, and proposes a fix."*

- Show the **pending incidents** — anomaly type, root cause, recommended fix
- Click an incident → show the detailed healing plan
- Click **"Approve Fix"** → watch it get resolved in real-time (WebSocket update)
- **Say:** *"In our experiments, OrchestrAI achieved 73% self-healing success rate with MTTR of 4.2 minutes, versus 28+ minutes for manual intervention."*

---

### 6. Cost Optimizer (1 min)
**URL:** http://localhost:3001/optimizer

> *"The Cost Optimizer agent rewrites expensive queries to reduce Snowflake credit consumption."*

- Show cost savings metrics
- **Say:** *"Achieved 34% average cost reduction across 30 benchmark queries."*

---

### 7. Data Lineage (30 sec)
**URL:** http://localhost:3001/lineage

> *"Full column-level lineage — we can trace any field from source PostgreSQL through transformations to the Snowflake destination."*

---

## 🧪 BACKUP: Run AI Analyst Queries via API

If the UI is slow, demo via curl:

```bash
curl -s -X POST http://localhost:8000/api/analyst/query \
  -H "Content-Type: application/json" \
  -H "X-Dev-Mode: true" \
  -d '{"question": "Show total revenue by region for 2025", "schema": "public"}' \
  | python3 -m json.tool
```

---

## 💡 KEY NUMBERS TO MENTION

| Metric | Value |
|--------|-------|
| Self-healing success rate | **73%** |
| Mean Time to Recovery | **4.2 min** (vs 28 min manual) |
| NL-to-SQL accuracy | **71.4%** on Spider v1.0 |
| Query cost reduction | **34%** avg |
| Demo dataset | **10,000 orders, 2,000 customers** |
| Active AI agents | **10** (LangGraph orchestrated) |
| Monitored pipelines | **4** (Postgres → Snowflake) |
| API endpoints | **28** REST + 1 WebSocket |

---

## 🔴 COMMON QUESTIONS & ANSWERS

**Q: Is Snowflake a real connection?**
> "Snowflake credentials are optional — the system falls back to a local PostgreSQL schema called `snowflake_dest` for the demo, which simulates the destination warehouse perfectly."

**Q: How does the self-healing work end-to-end?**
> "When a pipeline fails, the Monitoring Agent detects the anomaly type (zero-load, schema drift, etc.), the Diagnosis Agent identifies the root cause using ML (Isolation Forest), the Healing Agent proposes the fix, and with Human-in-the-Loop approval, the Deployment Agent applies it. Everything is LangGraph-orchestrated."

**Q: Why Groq instead of OpenAI?**
> "Groq's inference is 10-25x faster than OpenAI for the llama-3.3-70b model — critical for real-time NL-to-SQL where users expect sub-2-second responses."

**Q: How does it handle SQL injection?**
> "All queries are validated by the Validation Agent before execution. We use psycopg2 parameterized queries, an allowlist of permitted operations (SELECT only), and schema-level access control."

---

## 🛑 STOP EVERYTHING

```bash
./stop_demo.sh
```
