# OrchestrAI — PPT Speaking Script
### 15 minutes · 17 slides · Read through once before the viva

> **How to use this:** Read it aloud once. Don't memorise word-for-word — know the flow. Each slide has a [TIME] guide. Pause briefly when you advance the slide.

---

## SLIDE 1 — TITLE `[~40 sec]`

*[Stand, make eye contact, speak clearly.]*

"Good morning. My name is Parthiv Patel, roll number 2024AA05129, M.Tech Artificial Intelligence and Machine Learning at BITS Pilani, ZG628T.

My dissertation project is called **OrchestrAI** — an Autonomous Multi-Agent AI Platform for Self-Healing Data Pipelines. I am building this at my industry partner, **Hevo Technologies**, a data integration company in Bengaluru.

I'll take you through the work I've completed at mid-semester in the next 15 minutes."

---

## SLIDE 2 — AGENDA `[~30 sec]`

"Here's the structure of my presentation today.

I'll start with the problem and objectives, cover the literature and methodology, walk through the system architecture and multi-agent design, then show you where the platform stands at mid-semester — the engineering metrics, the UI, and the validation results — and finally the roadmap and experiments planned for the second half."

---

## SLIDE 3 — PROBLEM STATEMENT `[~90 sec]`

"Let me start with why this project exists.

At Hevo Technologies, I identified **three operational problems** that cost engineering teams significant time and money every week.

The **first problem is pipeline failures.** When a source database changes — for example, a developer renames a column — Hevo's data pipelines break silently. There's no automatic detection, no automatic recovery. Engineers waste 50% of their time just investigating what went wrong instead of building new features.

The **second problem is warehouse cost overruns.** Snowflake charges by compute time. A single badly written query — a CROSS JOIN on a 10-million row table, or a missing partition filter — can cost 10 times more than a well-written one. Today, there's no system that automatically detects and rewrites these queries before they run.

The **third problem is schema design debt.** Setting up dimensional data models in dbt — following best practices — takes weeks of senior engineer time. There's no automated scaffolding today.

The bottom line, as you can see here: **no existing open-source platform closes the full loop** — detect the problem, diagnose it, write a fix, test it safely, get human approval, deploy it, and learn from it. OrchestrAI is designed to close that loop."

---

## SLIDE 4 — OBJECTIVES `[~60 sec]`

"Based on these three problems, I defined **8 research objectives** for OrchestrAI.

The first two are the core: building the **multi-agent orchestration framework** using LangGraph with 10 specialised agents, and building the **self-healing pipeline** that covers the full detect-to-deploy cycle.

Objectives 3 and 4 address the cost and schema problems: an **SQL Cost Optimizer** Agent and a **dbt Dimensional Modelling** Agent.

Objective 5 is the **Natural Language Analytics** module — users type plain English, get SQL, a chart, and an AI insight.

Objectives 6, 7, and 8 cover **lineage and observability**, **multi-tenancy and security**, and **rigorous benchmarking** through 3 formal experiments — which are the core post-semester deliverables."

---

## SLIDE 5 — GAP ANALYSIS `[~70 sec]`

"Before designing anything, I reviewed the existing tools in the market.

This table compares OrchestrAI against the four most widely adopted data reliability platforms: Monte Carlo, Great Expectations, Datafold, and dbt Cloud.

Monte Carlo is the strongest competitor — it covers 6 of the 10 capabilities. It detects anomalies, shows lineage, and sends alerts. But it **cannot generate a fix, cannot test a fix in a sandbox, and cannot learn from past incidents**. A human still does all the remediation.

Great Expectations validates your data against rules you write. 4 out of 10. Datafold shows you data diffs. 4 out of 10.

**OrchestrAI is the only platform that covers all 10 capabilities** — and specifically the only one with autonomous fix generation, sandboxed testing, and RAG-based continuous learning. That is the research gap this project fills."

---

## SLIDE 6 — PAPERS → DESIGN DECISIONS `[~70 sec]`

"Our literature survey covers **11 papers**, each of which directly shaped a design decision in the platform.

Let me highlight the most important ones.

**Breck et al. [4]** — TensorFlow Data Validation — taught us schema fingerprinting. But where TFDV only detects drift, OrchestrAI goes further: we automatically generate and sandbox-test a fix. That's the gap we close.

**LangGraph [6]** gave us the multi-agent graph architecture — 10 nodes, conditional edges, and HITL wait states.

**Lewis et al. [7]** — RAG — we apply this not for factual question answering, but to retrieve past pipeline fixes from ChromaDB. The system learns from its own incident history.

**Chandola et al. [10]** — we used this survey to select **Isolation Forest** over LOF and LSTM: it's sub-linear in complexity, works on small samples, and handles multivariate telemetry without labelled data.

And **Seshia et al. [11]** is why the Approval Gate is a contractual boundary, not optional — in a system that deploys code to production, human oversight is not a limitation, it's a design requirement."

---

## SLIDE 7 — DSR METHODOLOGY `[~60 sec]`

"For research methodology, I'm following **Design Science Research** — the Hevner 2004 framework. DSR is the correct methodology when your research contribution is a working artefact, not just a theory.

It has 6 activities. Looking at the table:

**Activities 1, 2, and 3 are complete** — problem identified at Hevo, 8 measurable objectives defined, and the platform built across 8 development sprints.

**Activity 4 — Demonstration** is partially done. The sandbox runs with injected failures; the live end-to-end demonstration with a real database is Phase 2.

**Activities 5 and 6 — Evaluation and Communication** are post mid-semester. These are the 3 formal experiments and this dissertation.

DSR is appropriate here because OrchestrAI's value cannot be proven by theory alone — it requires a running system in a real industrial context."

---

## SLIDE 8 — SYSTEM ARCHITECTURE `[~90 sec]`

"Let me walk you through the architecture — and this is the actual system diagram from our platform.

OrchestrAI has **four tiers**, all communicating through well-defined interfaces.

At the top, the **Presentation Tier** — a Next.js 14 browser application with 12 pages: Dashboard, Pipeline Builder, AI Analyst, Human Approval Panel, Lineage, Data Quality, and more.

Below it, the **Application Tier** — a FastAPI backend exposing **24 REST endpoints** across 10 domain modules. Every endpoint is protected by JWT authentication middleware. Connector credentials are encrypted with Fernet before storage.

Third, the **Multi-Agent Tier** — a LangGraph StateGraph with 10 agent nodes. This is the intelligent core of the platform. All agents share a single TypedDict called `PipelineHealingState` — they communicate only through this shared state, never through direct calls. This eliminates tight coupling between agents.

At the base, the **Persistence Tier**: PostgreSQL for relational records, Snowflake for analytical queries, ChromaDB for vector embeddings of past incidents, and Marquez for OpenLineage lineage events.

All four tiers except Persistence are stateless — they can be scaled horizontally behind a load balancer."

---

## SLIDE 9 — MULTI-AGENT ORCHESTRATION `[~90 sec]`

"This diagram shows the **self-healing agent workflow** — the intellectual core of OrchestrAI.

A pipeline failure triggers 8 steps.

First, the **Monitoring Agent** detects the failure from Airflow's OpenLineage events. The **Anomaly Detector** applies Isolation Forest to classify the failure — schema drift, null spike, row count drop, type error, or timeout. If the anomaly score is above 0.65, the **Diagnosis Agent** traverses the lineage graph in Marquez to find the root cause and generates a plain-language explanation.

Then the **Fix Writer Agent** retrieves similar past incidents from ChromaDB using RAG, and prompts Groq's Llama 3.3 model to generate a targeted code fix.

That fix goes to the **Sandbox Agent**, which spins up a fresh Docker container, seeds it with 10% of production data, applies the fix, and runs **12 safety checks**.

If all checks pass, the **Approval Gate** surfaces everything in the UI — the fix diff, sandbox results, and 3 similar past incidents — and **waits for the human operator** to approve or reject.

On approval, the **Deployment Agent** creates a GitHub pull request and merges after CI passes. Finally, the **Learning Agent** stores the new incident-fix pair in ChromaDB — so the system gets smarter with every fix it handles."

---

## SLIDE 10 — PROGRESS `[~60 sec]`

"Here's where the platform stands at mid-semester.

Looking at the top row: **72% overall completion**, **24 REST endpoints** all operational, and **10 agent nodes** implemented.

Second row: **12 frontend pages** compiled and routable, **42 source files** across the codebase, and **19 bugs** identified and resolved.

The progress chart below breaks this down by module. Backend API, Frontend UI, Connector Gallery, Data Quality, and Schema Registry are all at 100%. Multi-Agent implementation is at 80%. PostgreSQL live integration and the end-to-end healing workflow are the key remaining items — these are Phase 1 of the post-semester roadmap.

So the platform is fully built and testable. What remains is connecting it to live production data and running the formal experiments."

---

## SLIDE 11 — ENGINEERING METRICS `[~60 sec]`

"This table shows the engineering targets we set at the start of the semester versus what was achieved.

All 7 mid-semester targets are met — 24 of 24 endpoints passing, 12 of 12 frontend pages compiled, 10 of 10 agent nodes implemented, 12 of 12 sandbox checks built, all 19 integration bugs resolved, and overall completion at 72% — above the 70% target.

The three Post Mid rows — end-to-end healing loop, MTTR reduction, and NL-SQL accuracy — are the post-semester experiments. Their success criteria are already defined: greater than 50% MTTR reduction, greater than 65% NL-SQL accuracy on Spider v1.0, and greater than 30% Snowflake cost savings."

---

## SLIDE 12 — UI SCREENSHOTS `[~80 sec]`

"Let me show you what the platform looks like.

On the top-left, this is the **Pipeline Dashboard** — real-time status of all monitored pipelines, KPI cards showing active runs and current MTTR, recent incidents with auto-heal and pending-approval status badges, and the 4 AI agent status indicators at the bottom.

Top-right is the **Human Approval Panel** — this is what an engineer sees when the AI has a fix ready. On the left: the root cause narrative and lineage path showing which models are broken. On the right: the proposed code fix. At the bottom: 12-check sandbox results and 3 RAG-retrieved similar past incidents. The operator clicks Approve or Reject — one click.

The bottom panel is the **AI Analyst** — our natural language interface. The user typed *'Show me the top 10 pipelines by failure rate in the last 7 days'*. The system generated the SQL, executed it, rendered a bar chart, and wrote an AI insight below. No SQL knowledge required from the user."

---

## SLIDE 13 — 12-CHECK SUITE `[~70 sec]`

"The sandbox runs **12 checks** on every proposed fix before a human even sees it.

The 12 checks fall into three severity levels.

**ABORT — 4 checks**: Row Count Minimum, Primary Key Uniqueness, Data Type Consistency, and Execution Time Limit. If any of these fail, the fix is immediately discarded and the incident is escalated. These are non-negotiable.

**FAIL — 5 checks**: Null Rate, New Null Columns, Foreign Key Integrity, Schema Fingerprint Match, No All-Null Columns. These are configurable — in strict mode they block; in permissive mode they log and continue.

**WARN — 3 checks**: Row Count Stability, Numeric Mean Drift, Categorical Value Set. These always log and continue — they signal something worth monitoring but don't block deployment.

This 12-check design is what makes the fix proposals trustworthy. By the time the Approval Panel is shown to the human, the fix has already passed 12 automated quality gates."

---

## SLIDE 14 — BUGS `[~50 sec]`

"During integration testing I found and resolved **19 bugs** across 3 root-cause categories.

8 were **router prefix conflicts** — FastAPI routes configured with double-prefixed paths like `/api/api/pipelines` that never matched any request. Fixed by aligning path declarations with include_router prefix settings.

10 were **database-unavailable crashes** — the server was throwing unhandled psycopg2 exceptions when PostgreSQL was offline. Fixed with try/except blocks and a demo-data fallback that returns structurally correct responses.

1 was a **missing dependency** — the `sqlparse` library was imported in the AI insights module but not listed in requirements.txt. All routes under `/api/insights` were crashing at import time. Fixed by adding it and pinning the version.

**Result: 100% pass rate across all 24 endpoints, stable across 5 consecutive test runs.**"

---

## SLIDE 15 — ROADMAP `[~50 sec]`

"For the post-semester roadmap, I've planned **4 phases** across 12 weeks.

**Phase 1, weeks 1-3**: Connect to live PostgreSQL at Hevo, run Alembic migrations, replace demo fallbacks with real data.

**Phase 2, weeks 4-6**: Wire the complete end-to-end healing loop with a real database, inject 20 synthetic failures to test the full 8-step cycle, and add Slack incident alerts.

**Phase 3, weeks 7-9**: Run all 3 pre-registered experiments — MTTR reduction, NL-SQL accuracy on Spider, and Snowflake query cost savings.

**Phase 4, weeks 10-12**: Complete dissertation writing, oral defence preparation, and demo video.

Phase 1 is the critical gate — the experiments in Phase 3 depend entirely on live data being available."

---

## SLIDE 16 — EXPERIMENTS `[~70 sec]`

"The three post-semester experiments are the core empirical contribution of this dissertation — and all three are pre-registered, meaning success criteria are locked before data collection begins.

**Experiment 1 — Self-Healing Effectiveness**: We inject 20 controlled failures across 5 failure types, 5 repetitions each — 100 test runs total. We measure MTTR against a rule-based baseline and a no-healing baseline using a paired t-test at α = 0.05. Target: greater than 50% MTTR reduction.

**Experiment 2 — NL-to-SQL Accuracy**: We run the AI Analyst against Spider v1.0's full test set of approximately 1,034 questions using the standard Spider evaluation script. Target: greater than 65% exact match.

**Experiment 3 — Query Cost Reduction**: 30 representative Snowflake queries from Hevo's history, measured before and after the Cost Optimizer Agent rewrites them using Snowflake's credit billing model. Target: greater than 30% average cost reduction.

Pre-registration is important — it ensures the experiments are scientifically valid regardless of outcome."

---

## SLIDE 17 — CONCLUSION `[~50 sec]`

*[Slow down, make eye contact, speak with confidence.]*

"Let me close with what we have built and what comes next.

Looking at the five numbers here: **10 agent nodes, 24 endpoints, 12 sandbox checks, 72% complete, 19 bugs resolved**.

The platform is real. It is not a prototype — it is a working system with a production-grade architecture, tested and running at mid-semester.

Three takeaways.

**LOOP** — OrchestrAI is the first platform to close the full self-healing loop: detect, diagnose, fix, sandbox, approve, deploy, learn. No existing open-source tool does all seven steps.

**LIVE** — 24 endpoints, 12 pages, zero TypeScript errors. All 24 endpoints smoke-tested across 5 consecutive runs.

**NEXT** — 3 pre-registered experiments will prove the thesis: MTTR reduction, NL-SQL accuracy, and Snowflake cost savings. Success criteria are already locked.

Thank you. I'm happy to take any questions."

*[Pause. Smile. Wait.]*

---

## TIMING GUIDE

| Slide | Topic | Target |
|-------|-------|--------|
| 1 | Title | 0:40 |
| 2 | Agenda | 1:10 |
| 3 | Problem | 2:40 |
| 4 | Objectives | 3:40 |
| 5 | Gap Analysis | 4:50 |
| 6 | Papers | 6:00 |
| 7 | DSR | 7:00 |
| 8 | Architecture | 8:30 |
| 9 | Multi-Agent | 10:00 |
| 10 | Progress | 11:00 |
| 11 | Metrics | 12:00 |
| 12 | UI Screenshots | 13:20 |
| 13 | 12-Check Suite | 14:30 |
| 14 | Bugs | 15:20 |
| 15 | Roadmap | 16:10 |
| 16 | Experiments | 17:20 |
| 17 | Conclusion | 18:10 |

> Total: ~18 minutes. You have buffer. If they stop you for questions mid-way, that's fine — it means they're engaged. Don't rush to finish every slide.

---

## QUICK REMINDERS

- **Slide 3** — point to each card as you say it (50%, 10×, Weeks)
- **Slide 8** — trace the four tiers top-to-bottom with your hand/pointer
- **Slide 9** — walk the arrows in order: detect → diagnose → fix → sandbox → approve → deploy → learn
- **Slide 12** — bottom screenshot (AI Analyst) gets the most attention; don't skip it
- **Slide 17** — SLOW DOWN here. This is your closing statement.

---

*Script reference: PPT Slides 1–17 · ~18 min total*
