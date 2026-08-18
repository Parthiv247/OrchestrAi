# OrchestrAI — 15-Minute Viva Speech & Demo Script

> **Timing guide:** Each section shows target clock time. Speak at a natural pace — not too fast.
> **[DEMO]** = switch to screen / click something. **[SLIDE]** = point to slide.

---

## ⏱ 0:00 – 1:00 | OPENING (1 minute)

> *Stand confidently. Make eye contact. Don't rush.*

"Good morning / Good afternoon.

My name is Parthiv Patel, and my MTech final-semester project is **OrchestrAI** —
an Autonomous Multi-Agent AI Platform for Self-Healing Data Pipelines.

In today's data-driven world, companies run hundreds of data pipelines every single day —
pipelines that move data from databases into analytics systems, data warehouses, BI tools.
And these pipelines break. Constantly.

My project asks one question: **what if the system could detect, diagnose, and fix itself —
without a human waking up at 3am to do it?**

That's OrchestrAI."

---

## ⏱ 1:00 – 3:00 | THE PROBLEM (2 minutes)

"Let me start with why this problem is hard.

A typical enterprise data team maintains 50 to 200 pipelines running on a schedule.
When a pipeline fails — say, the source table lost 80% of its rows overnight,
or a new column appeared in the schema that the downstream model wasn't expecting —
the process today looks like this:

An alert fires at 2am. An on-call engineer gets paged.
They spend 20 to 40 minutes reading logs, understanding the root cause,
writing a fix, testing it, and deploying it.

This is called the **Mean Time To Recover**, or MTTR.
Industry average for data pipeline failures: around 40 minutes.

The second problem is **query cost**. Data teams run hundreds of SQL queries against
cloud data warehouses like Snowflake or BigQuery, which charge by the byte scanned.
A single poorly-written query — a SELECT star, or a correlated subquery —
can cost thousands of dollars per month.

And the third problem is **compliance**. Under GDPR and India's PDPA, companies must
know where personal data lives across all their systems.
Manually auditing every column in every table is expensive and error-prone.

OrchestrAI solves all three."

---

## ⏱ 3:00 – 5:00 | ARCHITECTURE (2 minutes)

> *[SLIDE — architecture diagram]*

"OrchestrAI is built as a **10-agent multi-agent system** orchestrated by LangGraph.

Let me walk through the agent hierarchy quickly:

**Layer 1 — Detection:**
The MonitoringAgent runs continuously, feeding pipeline metrics into
a pre-trained **IsolationForest** model — an unsupervised anomaly detection algorithm.
When it detects an anomaly, a **RandomForest classifier** categorises the failure type —
volume drop, schema drift, null spike, consecutive failures, or pipeline delay.

**Layer 2 — Diagnosis:**
The DiagnosisAgent takes the classified failure and runs root-cause analysis —
cross-referencing pipeline logs, upstream source counts, and schema snapshots.
It produces a root-cause string with a confidence score.

**Layer 3 — Healing:**
Based on the failure type, the HealingOrchestrator dispatches the right specialist agent:
the SchemaFixAgent, the VolumeRecoveryAgent, or the FreshnessAgent.
These agents generate a fix, test it, and — if confidence is high enough —
send it for human approval before deploying.

**Layer 4 — Analytics & Optimization:**
Separately, the QueryAgent translates natural language questions into SQL using Groq's
LLaMA 3.3 70B model. The CostOptimizerAgent rewrites expensive queries.
The DbtModelingAgent manages our transformation layer using dbt.
And the LearningAgent tracks every healing outcome and improves strategy selection over time.

The entire backend is **FastAPI**, the frontend is **Next.js 14**,
and the database layer uses **PostgreSQL + ChromaDB** for vector embeddings."

---

## ⏱ 5:00 – 12:00 | LIVE DEMO (7 minutes)

> *Switch to browser. App is running at localhost:3001*

---

### 5:00 – 5:45 | Dashboard

> **[DEMO — open Dashboard]**

"This is the OrchestrAI dashboard.

You can see the live system health at a glance —
**2 active pipelines**, **2 incidents pending approval**,
overall success rate, and the ML model status.

The metric cards update in real-time via WebSocket connections —
so when a pipeline run completes, the dashboard reflects it instantly.

The activity feed on the right shows a live log of all recent agent actions."

---

### 5:45 – 6:30 | Pipelines

> **[DEMO — click Pipelines in sidebar]**

"Here are our active pipelines.

**Postgres to Snowflake** — this is our primary ETL pipeline.
It extracts from our PostgreSQL source — which holds the e-commerce B2B dataset —
and syncs to Snowflake as the destination.

**CRM Sync Pipeline** — a secondary pipeline syncing customer relationship data.

You can see the last run status, duration, and schedule for each.
Clicking into a pipeline shows full run history and logs."

---

### 6:30 – 7:30 | Approvals — Self-Healing in Action

> **[DEMO — click Approvals in sidebar]**

"This is the most important page in the demo — this is where **self-healing becomes visible**.

You can see **2 incidents pending human approval**.

The first: **orders_to_snowflake** — the IsolationForest detected a 78% volume drop
in the source table. The root cause confidence is **91%** — the upstream ETL failed.
The system has already generated a fix and is waiting for a human to approve deployment.

The second: **crm_sync_pipeline** — a schema drift incident.
A new column called 'customer_tier' appeared in the source schema.
The system detected the drift, identified that the dbt staging model needs regeneration,
and is waiting for approval.

In a real production system, low-confidence incidents get flagged for human review.
High-confidence ones — above a configurable threshold — can be auto-approved.

This is **Human-in-the-Loop AI** — the system does the heavy lifting,
but keeps humans in control of deployment decisions."

---

### 7:30 – 8:30 | AI Analyst — Natural Language to SQL

> **[DEMO — click AI Analyst in sidebar]**

"Now let me show the AI Analyst.

This page lets a business user — someone who doesn't know SQL —
ask questions about the data in plain English.

Let me type: *'What are the top 5 product categories by total revenue?'*

> *[Type the question and submit]*

Under the hood, this sends the question to **Groq's LLaMA 3.3 70B** model
along with our schema context. The model generates a SQL query,
we execute it against our mart tables, and return the result as both
a data table and a chart.

This is exactly the NL-to-SQL capability that democratises data access —
your sales manager can get pipeline insights without waiting for a data analyst."

---

### 8:30 – 9:15 | Cost Optimizer

> **[DEMO — click Cost Optimizer in sidebar]**

"The Cost Optimizer shows our cumulative query savings — currently **$284.73 saved**.

The history below shows past optimizations.

The first example rewrote a **SELECT star with no column filter** into an explicit
column selection with a LIMIT — saving 84.5% of query cost.

The second rewrote a **correlated subquery** — which executes once per row —
into a standard JOIN, saving 82.8%.

In cloud data warehouses that charge per byte scanned,
these rewrites directly reduce the monthly bill."

---

### 9:15 – 10:15 | dbt Transformation

> **[DEMO — click dbt in sidebar]**

"This is our dbt integration — dbt stands for Data Build Tool.

dbt sits between our raw pipeline data and our analytics layer.
It transforms raw, messy source tables into clean, analytics-ready fact and dimension tables.

The SQL editor here shows one of our mart models — **fct_revenue_by_category**.
This is a 26-line CTE query that:
- Joins order_items to products and orders
- Filters only completed and shipped orders
- Groups monthly revenue by product category
- And adds a window function to calculate each category's revenue share percentage

The DbtModelingAgent can introspect raw tables and auto-generate models like this.

Below, you can see the **dbt run history** — our last run completed 8 models
successfully with 16 data quality tests all passing."

---

### 10:15 – 11:00 | Data Quality + PII Scanner

> **[DEMO — click Data Quality in sidebar]**

"Data Quality shows our schema registry and quality rule results.

We have 5 rules running:
- Not-null check on order amounts — critical, passing
- Email uniqueness check — critical, passing
- Amount range check — warning, passing
- Data freshness check — critical, passing
- Row count minimum — warning, passing

> **[DEMO — click PII Scanner tab]**

The PII Scanner runs a two-pass analysis.
Pass 1 uses regex patterns on column names.
Pass 2 sends ambiguous columns to Groq's LLM for verification.

It found 5 PII columns across our schema —
customers.email, customers.phone, customers.date_of_birth, payments.card_number.
These are now tagged in the data catalog for governance and access control."

---

### 11:00 – 12:00 | Observability + ML Model Health

> **[DEMO — click Observability in sidebar]**

"Finally, observability.

The SLA tracker shows our two pipelines — orders_to_snowflake at **96.5% success rate**,
and crm_sync at **94.4%**.
P95 latency — the slowest 5% of runs — is under 95 seconds.

The daily timeline below shows error rates over the last 7 days,
so you can spot patterns — for example, higher error rates on weekends
when upstream data volumes drop.

And this panel — ML Model Health — is our anomaly detection system's live status.

**IsolationForest:** ROC-AUC of 0.896 — detecting anomalies with 89.6% accuracy.
The classifier runs on 5 failure types — zero load, row count drop, null spike,
consecutive failures, and pipeline delay.

Trained on 2,000 synthetic failure scenarios."

---

## ⏱ 12:00 – 14:00 | RESULTS (2 minutes)

> *[SLIDE — ablation study / results table]*

"Now let me talk about our evaluation results.

We ran a controlled experiment — **20 failure scenarios**, 5 repetitions each,
across 3 system configurations.

**Manual baseline:** Average MTTR of 2,375 seconds — about 40 minutes.
**Rule-based only:** 601 seconds — about 10 minutes.
**Full OrchestrAI:** **134 seconds — just over 2 minutes.**

That's **17.7 times faster than manual intervention**,
and **4.5 times faster than rule-based systems**.
Statistical significance: p < 0.001 — this is not noise.

For NL-to-SQL accuracy, we tested 50 natural language questions against their
reference SQL on a representative query set.
OrchestrAI achieved **72% exact match accuracy** — above our 65% target.

For the cost optimizer, across 30 queries,
we achieved an average cost reduction of **83.4%** —
significantly exceeding our 30% target.

The system makes real, measurable improvements across all three problem dimensions."

---

## ⏱ 14:00 – 15:00 | CONCLUSION (1 minute)

"To summarise:

OrchestrAI is a production-ready, multi-agent AI platform that:
1. **Detects** pipeline failures using IsolationForest ML — in seconds, not minutes
2. **Diagnoses** root causes using LangGraph agent orchestration
3. **Heals** pipelines autonomously with human-in-the-loop approval
4. **Optimises** query costs using LLM-powered rewriting
5. **Ensures compliance** with automated PII discovery
6. And **democratises data access** through natural language querying

The system is fully containerised with Docker, secured with JWT authentication,
and backed by a complete test suite and CI/CD pipeline.

The core academic contribution is demonstrating that a **collaborative multi-agent architecture**
outperforms both manual intervention and single-agent rule-based systems
by a statistically significant margin.

Thank you. I'm happy to take questions."

---

## 💡 LIKELY VIVA QUESTIONS — Quick Answers

**Q: Why LangGraph over plain LangChain?**
LangGraph gives us stateful graphs with cycles — essential for retry logic and conditional
healing paths. LangChain is stateless; LangGraph lets agents loop back on failure.

**Q: Why IsolationForest specifically?**
It's unsupervised — no labelled failure data needed to start.
It works well with high-dimensional tabular metrics and is interpretable.
ROC-AUC 0.896 validates the choice empirically.

**Q: What if the LLM generates wrong SQL?**
We have a ValidationAgent that runs EXPLAIN on the generated query before execution.
We also enforce read-only access — no DML allowed through the analyst interface.

**Q: How does the system learn over time?**
The LearningAgent writes every healing outcome to the healing_outcomes table —
success/failure, time taken, fix type. It uses this history to weight strategy selection
for future incidents of the same type.

**Q: Why Groq instead of OpenAI?**
Groq's LPU hardware gives sub-second inference latency — critical for real-time
NL-to-SQL responses. Cost is also lower at scale.

**Q: What are the limitations?**
Three main ones: (1) Groq API dependency — if the service is down, NL-SQL fails gracefully.
(2) IsolationForest needs retraining as pipeline characteristics drift over time.
(3) The current system handles structured SQL pipelines — unstructured data pipelines
(streaming, ML model serving) are future work.

**Q: How is this different from existing tools like Airflow or Monte Carlo?**
Airflow orchestrates pipelines but doesn't heal them — it just retries.
Monte Carlo detects anomalies but requires human remediation.
OrchestrAI is the only system that closes the full loop: detect → diagnose → heal → learn,
autonomously, with LLM-powered root-cause analysis.
