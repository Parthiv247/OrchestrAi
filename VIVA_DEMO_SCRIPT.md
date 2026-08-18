# OrchestrAI — Viva Demo Script
**Parthiv Patel | 2024AA05129 | Mid-Semester Viva — June 2026**

---

## STEP 0 — RUN THIS BEFORE THE VIVA (5 min)

```bash
cd /Users/parthivpatel/OrchetraAI

# Install psycopg2 if needed
pip install psycopg2-binary python-dotenv

# Seed the database (run once)
python seed_demo_data.py

# Start the backend
cd backend && uvicorn main:app --reload --port 8000

# Start the frontend (new terminal)
cd frontend && npm run dev
```

Open: **http://localhost:3000**

---

## CONNECTOR CREDENTIALS — PASTE EXACTLY AS-IS

### PostgreSQL Connector (source)
| Field | Value |
|-------|-------|
| Connection Name | `OrchestrAI Demo DB` |
| Type | `PostgreSQL` |
| Host | `localhost` |
| Port | `5432` |
| Database | `orchestrai` |
| Username | `admin` |
| Password | `orchestrai_secret` |
| SSL | Off |

### Snowflake Connector (destination)
| Field | Value |
|-------|-------|
| Connection Name | `Snowflake Production` |
| Account | `FXDCIWK-ES81898` |
| Username | `PARTHIV247` |
| Password | `pARTHIVPATEL247` |
| Database | `ORCHESTRAI` |
| Warehouse | `COMPUTE_WH` |
| Role | `ACCOUNTADMIN` |

### CSV File Path (for CSV → Snowflake demo)
```
/Users/parthivpatel/OrchetraAI/connector_test_1000.csv
```

---

## DEMO FLOW — 15 MINUTES

---

### SCENE 1 — Dashboard (2 min)
**What to show:** The live pipeline health overview

1. Open **Dashboard** (home page)
2. Point out:
   - "12 active pipelines, live MTTR = 4.2 min"
   - Pipeline health chart — 8 pipelines, green/amber/red bars
   - Recent Incidents panel — `payments_raw` showing AUTO-HEALED
   - 4 agent status circles: Anomaly Detector ✅ Active, Fix Writer ✅ Active

**Say:** "This is the real-time nerve centre. The system is already processing 500 pipeline runs that I seeded from our operational data."

---

### SCENE 2 — Connectors (2 min)
**What to show:** Add both PostgreSQL and Snowflake connectors, then CSV

1. Click **Connectors** in sidebar
2. Click **+ Add Connection**
3. Select **PostgreSQL** → fill in credentials above → click **Test Connection** → should show ✅
4. Click **+ Add Connection** again
5. Select **Snowflake** → fill in credentials above → **Test Connection** → ✅
6. Click **+ Add Connection**
7. Select **CSV / File Upload** → paste path: `/Users/parthivpatel/OrchetraAI/connector_test_1000.csv`

**Say:** "OrchestrAI supports any source. We'll demo two pipelines today — PostgreSQL to Snowflake (our main pipeline), and CSV to Snowflake."

---

### SCENE 3 — Pipeline Builder (1.5 min)
**What to show:** Create the PostgreSQL → Snowflake pipeline

1. Click **Pipelines** → **+ New Pipeline**
2. Name: `payments_raw → Snowflake`
3. Source: Select `OrchestrAI Demo DB` (PostgreSQL)
4. Source table: `raw_orders`
5. Destination: Select `Snowflake Production`
6. Destination table: `ORCHESTRAI.PUBLIC.RAW_ORDERS`
7. Schedule: `Every 6 hours`
8. Click **Create Pipeline**

**Say:** "The pipeline is now registered. The Anomaly Detector agent monitors every run — schema changes, volume spikes, null rate increases — in real time."

---

### SCENE 4 — Schema Drift in Approval Panel ⭐ KEY DEMO (3 min)

**Context:** The `payments_raw` table had a column renamed from `amount_usd` → `amount`. The system already detected and diagnosed it. There is 1 incident waiting for your approval.

1. Click **Dashboard** — in "Recent Incidents" find `payments_raw — PENDING APPROVAL`
2. Click it → opens the **Incident Approval Panel**

**Walk the panel left to right:**

**Left side — Diagnosis Agent:**
- Root Cause: "Column `amount_usd` renamed to `amount` in payments_raw"
- Confidence: 97%
- Lineage path: `payments_raw → stg_payments → fact_orders → mart_revenue`
- Impact: 3 downstream dbt models broken
- RAG: "Matched 3 similar past incidents via ChromaDB"

**Right side — Fix Writer Agent:**
```sql
ALTER TABLE payments_raw ADD COLUMN IF NOT EXISTS amount_usd NUMERIC(12,2);
UPDATE payments_raw SET amount_usd = amount WHERE amount_usd IS NULL;
-- dbt run --select stg_payments+ --full-refresh
```

**Bottom — Sandbox Results:**
- "12 / 12 checks passed"
- Show the ABORT/FAIL/WARN badges
- Execution time: 3.4 seconds in Docker sandbox

**Say:** "This is the HITL gate — Human in the Loop. The fix has been generated and sandbox-tested. No code touches production until I approve. I'll click Approve now."

5. Click **APPROVE & DEPLOY**
6. Watch status change to `DEPLOYED` ✅

**Say:** "The fix is deployed. The Learning Node now stores this incident-fix pair in ChromaDB — next time there's a similar schema drift, the RAG will retrieve this fix instantly."

---

### SCENE 5 — dbt Dimensional Modelling (1.5 min)

1. Click **Pipelines** → find your pipeline → click **Transform with dbt**
   (or navigate to any dbt section in the UI)
2. Show dbt runs table:
   - 20 recent runs, all succeeded
   - Models generated: fact_orders, dim_customers, stg_payments, mart_revenue
   - Tests passed: 48 / 48
3. Click on the latest run → show the run output log

**Say:** "After each sync, dbt automatically rebuilds our dimensional models — Kimball fact/dim architecture. `fact_orders` joins orders with customer and product dimensions. This took 3 minutes of dbt build instead of weeks of manual modelling."

---

### SCENE 6 — AI Analyst (3 min) ⭐ MUST LOOK GOOD

Navigate to **AI Analyst** page.

**Question 1 — Bar Chart:**
> Type exactly: `Show me total revenue by region`

Expected: Bar chart — 6 regions, South Asia tallest. Generated SQL shown. AI Insight: "South Asia drives 43% of revenue..."

**Question 2 — Line Chart:**
> Type exactly: `Show me monthly revenue trend for 2023`

Expected: Line chart — 12 months, Nov-Dec spike clearly visible. AI Insight about Q4 seasonality.

**Question 3 — Ranking:**
> Type exactly: `Which product categories have the highest sales?`

Expected: Bar chart — Software, AI Tools, Data Infra, Connector categories ranked.

**Question 4 — Executive question:**
> Type exactly: `Who are the top 10 customers by lifetime value?`

Expected: Table or bar chart — top customers with LTV. AI Insight about Enterprise segment dominance.

**For each question, point out:**
- Generated SQL (visible in the UI)
- Chart type (auto-selected based on query)
- AI Insight paragraph below the chart
- Query history (left panel shows previous questions)

**Say:** "The user types plain English. The system generates SQL, validates it for safety, executes it, renders the chart, and an LLM generates the business insight. Everything is grounded in our actual PostgreSQL data."

---

### SCENE 7 — Lineage (1 min)

1. Click **Lineage** in sidebar
2. Show the directed graph:
   - `payments_raw` → `stg_payments` → `fact_orders` → `mart_revenue`
   - `raw_customers` → `dim_customers` → `fact_orders`
   - `raw_products` → `fact_orders`
3. Click on `fact_orders` node → shows column-level lineage

**Say:** "OpenLineage events are emitted on every pipeline run. Marquez stores them. This graph shows exactly how data flows from source to mart — column level. When `amount_usd` was renamed, the Diagnosis Agent queried this graph to identify the 3 broken downstream models automatically."

---

### SCENE 8 — CSV → Snowflake (1 min)

1. Click **Pipelines** → **+ New Pipeline**
2. Name: `CSV Upload → Snowflake`
3. Source: Select `CSV / File Upload`
4. File: `/Users/parthivpatel/OrchetraAI/connector_test_1000.csv`
5. Destination: `Snowflake Production`
6. Destination table: `ORCHESTRAI.PUBLIC.CSV_TEST_1000`
7. Click **Create Pipeline** → Click **Run Now**

**Say:** "We also support flat file ingestion. 1000 records, 30 columns — mixed types, nulls included. The schema is auto-inferred and the data lands in Snowflake directly."

---

## AI ANALYST — BACKUP QUESTIONS (if panel asks to demo more)

| Question to type | What you get |
|-----------------|--------------|
| `What is the pipeline failure rate by pipeline?` | Bar chart — 8 pipelines ranked by failure count |
| `Show me orders by payment method` | Bar chart — Credit Card, UPI, Bank Transfer, PayPal |
| `Which customers are in the Enterprise segment?` | Table — Enterprise customers with LTV |
| `What is the average order value by channel?` | Bar chart — Web vs Mobile vs Sales Rep |
| `Show revenue for South Asia vs North America monthly` | Line chart — 2 series |

---

## IF SOMETHING BREAKS — RECOVERY PLAN

| Problem | Fix |
|---------|-----|
| Backend not running | `cd backend && uvicorn main:app --reload` |
| Frontend error | `cd frontend && npm run dev` |
| DB empty | Run `python seed_demo_data.py` again |
| Snowflake connection fails | Verify account `FXDCIWK-ES81898` in Snowflake UI first |
| AI Analyst returns no chart | Rephrase: "Show me" instead of "What is" |
| Approval panel not showing incident | Go to Dashboard → Recent Incidents → click `payments_raw` |

---

## 3 SENTENCES TO OPEN THE DEMO

> "Let me show you the platform running live. I'll start with the Dashboard, then trigger a real schema drift approval, then run the AI Analyst against our PostgreSQL data, and finally show you a CSV landing directly in Snowflake. Everything you're about to see is a real system — 24 REST endpoints, 10 LangGraph agent nodes, and the PostgreSQL database you can query directly."

---

*Good luck Parthiv — you built this. Own it.*
