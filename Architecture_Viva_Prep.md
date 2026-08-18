# OrchestrAI — Architecture Viva Prep
**Everything the invigilator can ask about system design**

---

## THE ONE-MINUTE OVERVIEW (memorise this first)

> "OrchestrAI is a four-tier platform. The Presentation Tier is a Next.js 14 browser application with 12 pages. The Application Tier is FastAPI exposing 24 REST endpoints, all JWT-protected. The Multi-Agent Tier is a LangGraph directed graph with 10 specialised agent nodes sharing a single TypedDict state object. The Persistence Tier uses PostgreSQL for relational records, Snowflake for analytics, ChromaDB for vector embeddings, and Marquez for lineage. All tiers are stateless except Persistence, so the first three can be horizontally scaled independently."

---

## TIER 1 — PRESENTATION TIER

**Framework:** Next.js 14 with App Router  
**12 Pages:** Dashboard, Pipelines, Pipeline Builder, Pipeline Detail, Connectors, AI Analyst, Data Quality, Lineage, Observability, Reports, Settings, Onboarding Wizard

**Key technical decisions:**
- **React Server Components** — pages load fast, no client-side data fetch on first paint
- **TanStack Query v5** — manages cache invalidation and background refresh; pipeline dashboard always shows live state
- **Tailwind CSS** — design system with CSS custom property tokens; light/dark theme in one pass
- **Cmd+K global command palette** — keyboard access to all platform sections

**Why Next.js over plain React?**
> App Router gives server-side rendering and file-based routing out of the box. Pipeline status dashboards need fresh data on load — SSR delivers that without an extra round-trip. Plain React would require separate routing setup and client-only fetches, adding latency.

---

## TIER 2 — APPLICATION TIER

**Framework:** FastAPI (Python)  
**24 REST endpoints** across 10 domain modules:

| Module | Endpoints | Key routes |
|--------|-----------|-----------|
| Auth | 2 | POST /api/auth/login, /api/auth/me |
| Pipelines | 4 | GET/POST /api/pipelines, GET /api/pipelines/{id}, POST /api/pipelines/{id}/run |
| ETL Engine | 3 | POST /api/etl/run, GET /api/etl/status, POST /api/etl/sync |
| Connectors | 4 | GET/POST /api/connectors, POST /api/connectors/{id}/test, DELETE |
| Data Quality | 3 | GET /api/quality/rules, POST /api/quality/check, GET /api/quality/drift |
| AI Analyst | 3 | POST /api/analyst/query, GET /api/analyst/history, POST /api/analyst/feedback |
| Incidents | 2 | GET /api/incidents, POST /api/incidents/{id}/approve |
| Observability | 1 | GET /api/observability/metrics |
| Settings | 1 | GET/PUT /api/settings |
| Reports | 1 | GET /api/reports |

**Security:**
- **JWT middleware** — validates signed token on every request before handler runs
- **Fernet symmetric encryption** — connector credentials encrypted at write, decrypted in memory only when connection test is triggered; never stored in plaintext
- **RBAC** — admin / analyst / viewer roles with per-endpoint permission checks
- **X-Dev-Mode bypass** — dev-only header that skips auth for rapid frontend iteration; disabled in production

**Why FastAPI over Flask/Django?**
> FastAPI auto-generates OpenAPI docs, enforces Pydantic request/response validation at runtime, and supports async natively — critical for running LangGraph agent invocations without blocking the server thread. Flask is synchronous by default. Django brings ORM overhead not needed here since we use SQLAlchemy separately.

---

## TIER 3 — MULTI-AGENT TIER

### THE 10 AGENTS — NAMES, ROLES, AND WHAT THEY READ/WRITE

**Healing Group (agents 1–8):**

| # | Agent | Reads from state | Writes to state |
|---|-------|-----------------|-----------------|
| 1 | **MonitoringAgent** | — | `pipeline_run` |
| 2 | **AnomalyDetectorNode** | `pipeline_run` | `anomaly_score`, `anomaly_class` |
| 3 | **DiagnosisNode** | `anomaly_class`, `pipeline_run` | `diagnosis`, `lineage_path` |
| 4 | **FixWriterNode** | `diagnosis`, `rag_hits` | `proposed_fix` |
| 5 | **SandboxNode** | `proposed_fix` | `sandbox_result` |
| 6 | **ApprovalGateNode** | `sandbox_result`, `proposed_fix` | `approval_status` |
| 7 | **DeploymentNode** | `approval_status`, `proposed_fix` | `deployment_outcome` |
| 8 | **LearningNode** | `proposed_fix`, `deployment_outcome` | ChromaDB (external) |

**Analytics Group (agents 9–10 + sub-agents):**

| # | Agent | What it does |
|---|-------|-------------|
| 9 | **QueryAgent** | Fetches schema → builds LLM prompt → generates SQL |
| 10 | **ValidationAgent** | AST-level safety check (blocks DROP/DELETE/TRUNCATE/UPDATE-no-WHERE) |
| + | **InsightAgent** | Generates 2–3 sentence plain-English interpretation of chart result |
| + | **CostOptimizerAgent** | Scans SQL for anti-patterns → generates optimised rewrite + credit savings estimate |
| + | **ModellingAgent** | Inspects new source schema → scaffolds Kimball fact/dim dbt model set |

---

### PipelineHealingState — THE EXACT TYPEDDICT

```python
class PipelineHealingState(TypedDict):
    pipeline_run:       dict          # Airflow run record from PostgreSQL
    anomaly_score:      float         # Isolation Forest score ∈ [0,1]
    anomaly_class:      str           # schema_drift | null_spike | row_drop | type_err | timeout
    diagnosis:          str           # Natural-language root-cause narrative
    lineage_path:       list[str]     # OpenLineage node IDs from source to failure
    proposed_fix:       str           # Unified diff of the code repair
    rag_hits:           list[dict]    # Top-k ChromaDB similar incidents
    sandbox_result:     dict          # {passed: bool, checks: list[CheckResult]}
    approval_status:    str           # pending | approved | rejected
    deployment_outcome: Optional[str] # pull_request_url | error_message
    retry_count:        int           # Fix Writer retry counter (max 3)
```

**Why TypedDict and not a class?**
> TypedDict is flat and serialisable — the graph can be checkpointed and replayed after interruption without custom serialisation logic. A dataclass would need `__dict__` unwrapping. A plain dict would lose type checking. TypedDict gives both.

**Why shared state and not direct agent calls?**
> No agent calls another agent's methods directly. Each node reads only its designated fields, updates only its designated outputs, and returns the merged state to the LangGraph executor. This eliminates tight coupling — adding a new agent (e.g., a Cost Impact Estimator before the Diagnosis node) requires zero changes to existing node implementations. Guo et al. [9] documented direct agent calls as the most common fragility source in multi-agent systems.

---

### CONDITIONAL EDGE ROUTING

```
MonitoringAgent
    ↓
AnomalyDetectorNode → [score < 0.65] → END (no anomaly)
    ↓ [score ≥ 0.65]
DiagnosisNode
    ↓
FixWriterNode ←────────────────────────┐
    ↓                                  │ retry (max 3)
SandboxNode → [ABORT check fails] → END (escalate)
    ↓ [all 12 checks pass]             │
ApprovalGateNode → [rejected] ─────────┘
    ↓ [approved]
DeploymentNode
    ↓
LearningNode → END
```

**Anomaly threshold:** τ = 0.65 (Isolation Forest score). Below this → no anomaly. Above → trigger Diagnosis.  
**Retry limit:** Fix Writer retries up to 3 times if Sandbox fails or operator rejects, with rejection reason appended as context.

---

## THE 8-STEP SELF-HEALING DATA FLOW

1. **Airflow DAG** emits OpenLineage event to Marquez on pipeline failure
2. **MonitoringAgent** detects failure, retrieves run record from PostgreSQL
3. **AnomalyDetectorNode** applies Isolation Forest to (row_count, null_rate, exec_duration, schema_fingerprint_delta) → classifies failure type
4. **DiagnosisNode** traverses OpenLineage lineage graph to root-cause transformation → generates natural-language narrative
5. **FixWriterNode** retrieves top-k similar past incidents from ChromaDB (RAG) → prompts Groq LLM with diagnosis + context → generates code diff
6. **SandboxNode** provisions Docker container, seeds with 10% production data, applies fix, runs 12-check suite
7. **ApprovalGateNode** surfaces fix + sandbox results + RAG-retrieved similar incidents in UI → blocks until operator responds
8. On approval: **DeploymentNode** creates GitHub PR, monitors CI, merges on green → **LearningNode** stores fix embedding in ChromaDB

---

## THE 5-STEP NL-TO-SQL DATA FLOW

1. Operator types plain-English question → `POST /api/analyst/query`
2. **QueryAgent** fetches current schema fingerprint from schema registry → builds schema-aware LLM prompt → Groq generates SQL
3. **ValidationAgent** parses SQL AST with SQLGlot → blocks DROP / DELETE / TRUNCATE / UPDATE-without-WHERE
4. Safe query executes against Snowflake or PostgreSQL → frontend selects chart type (bar for categorical X + numeric Y, line for time-series, scatter for two numerics)
5. **InsightAgent** generates 2–3 sentence plain-English interpretation displayed below chart

**Why SQLGlot for AST parsing?**
> SQLGlot is dialect-aware — it parses Snowflake SQL, PostgreSQL SQL, and BigQuery SQL with the same API. A regex-based safety check would miss `DELETE` written as `dElEtE` or inside a CTE. AST parsing is exact.

---

## TIER 4 — PERSISTENCE TIER

| Store | What it holds | Why this one |
|-------|--------------|-------------|
| **PostgreSQL** | Users, tenants, incidents, pipeline runs, connectors, fixes | ACID guarantees, relational joins, well-understood |
| **Snowflake** | Analytical queries, data warehouse for customer data | Columnar, auto-scaling, pay-per-query — the industry standard for analytics workloads |
| **ChromaDB** | Vector embeddings of past incidents + fixes | Lightweight, Python-native, no infrastructure overhead; Weaviate is the planned production upgrade |
| **Marquez** | OpenLineage lineage events and graph | Open standard server for OpenLineage; powers the Lineage page DAG |

**Why not one database for everything?**
> PostgreSQL can't do vector similarity search efficiently. ChromaDB can't do ACID transactions. Snowflake is pay-per-query — using it for transactional writes would be expensive. Each store is chosen for what it does best.

---

## TECHNOLOGY STACK — FULL TABLE

| Tier | Component | Technology | Why selected over alternatives |
|------|-----------|-----------|-------------------------------|
| Presentation | Framework | Next.js 14 | SSR + App Router; React-only would need extra routing |
| Presentation | State/cache | TanStack Query v5 | Background refresh, cache invalidation built-in |
| Presentation | Styling | Tailwind CSS | Token-based design system, dark mode trivial |
| Application | API framework | FastAPI | Async, auto-docs, Pydantic validation; Flask = sync |
| Application | Auth | JWT (python-jose) | Stateless, horizontally scalable; sessions would need Redis |
| Application | Encryption | Fernet (cryptography) | Symmetric, authenticated; AES-CBC without auth tag is unsafe |
| Application | ORM | SQLAlchemy 2.0 | Async support, explicit query control; Django ORM = bloat |
| Agent | Orchestration | LangGraph | Directed graph with conditional edges; AutoGen = conversational |
| Agent | LLM | Groq (Llama 3.3 70B) | Sub-second latency; OpenAI GPT-4 = 10× higher cost |
| Agent | Tracing | LangSmith | Full agent run tracing, token count, latency per node |
| Agent | Vector DB | ChromaDB | Python-native, zero infrastructure; Weaviate = production path |
| Agent | SQL safety | SQLGlot | Dialect-aware AST parser; regex = bypassable |
| Agent | Anomaly detection | Isolation Forest (scikit-learn) | O(n log n), no label data, multivariate; LOF = O(n²) |
| Persistence | Relational DB | PostgreSQL | ACID, mature, free; MySQL = weaker JSON support |
| Persistence | Analytics DW | Snowflake | Columnar, serverless scaling; BigQuery = GCP lock-in |
| Persistence | Lineage | OpenLineage + Marquez | Open standard; proprietary tools = vendor lock |
| Data pipeline | Orchestration | Airflow | Industry standard, DAG-based; Prefect = less mature |
| ETL | dbt | dbt-core | Standard for SQL transformation; custom scripts = no lineage |
| Sandbox | Isolation | Docker | Portable, consistent; VMs = too heavy for per-fix testing |

---

## CONSTRAINTS AND ASSUMPTIONS — EXACT FROM REPORT

These are in Section 4.4 — know them, the invigilator may probe:

1. **No SSH tunnelling** — connectors must be TCP-reachable from the server host
2. **Groq API dependency** — if Groq is down, AI Analyst and PII LLM pass degrade gracefully (regex-only PII, error message in analyst)
3. **Single-process ETL** — FastAPI BackgroundTasks, not Celery; sufficient for prototype, not for concurrent pipelines at scale. Production upgrade: Celery + Redis
4. **Isolation Forest trained on synthetic data** — retraining on real Hevo production telemetry is Phase 2 after live DB integration
5. **Docker must be available on host** — sandbox doesn't support remote Docker; local only
6. **Multi-tenancy via JWT claims only** — PostgreSQL Row-Level Security (RLS) not yet enabled; noted as pre-production hardening step

**Key answer if asked:** "Every constraint is a known simplification with a documented production upgrade path. Replacing BackgroundTasks with Celery requires changing only the task dispatch call site — routes, agent graph, and DB models stay untouched. This upgrade-path transparency was a deliberate design goal."

---

## LIKELY INVIGILATOR QUESTIONS — ARCHITECTURE

---

**"Draw me the architecture."**

> Four boxes stacked vertically:  
> [Browser / Next.js 14 — 12 pages]  
> ↕ REST + JSON + JWT  
> [FastAPI — 24 endpoints — JWT middleware — Fernet encryption]  
> ↕ in-process Python calls  
> [LangGraph — 10 agent nodes — PipelineHealingState TypedDict]  
> ↕ DB drivers  
> [PostgreSQL | Snowflake | ChromaDB | Marquez]

---

**"What is PipelineHealingState and why is it a TypedDict?"**

> It's the sole communication contract between all 10 agent nodes. A flat, serialisable Python TypedDict with 11 fields covering the full lifecycle from anomaly score to deployment outcome. TypedDict because it's flat (checkpointable after interruption), type-checked (no field name typos), and serialisable (no custom `__dict__` unwrapping like a dataclass would need).

---

**"Why LangGraph and not AutoGen or CrewAI?"**

> LangGraph gives explicit typed-edge conditional routing — I can branch on ABORT vs WARN severity. AutoGen uses conversational multi-agent patterns with agents sending text messages to each other — hard to enforce deterministic flow in a production pipeline context. CrewAI is higher abstraction but less flexible for custom state graphs. LangGraph is the only one that natively supports HITL wait states (blocking graph execution until an external action — the operator's approval — occurs).

---

**"What happens if the Fix Writer generates a fix that passes all 12 sandbox checks but is still wrong?"**

> The Approval Gate is the last defence. Even a fix that passes all 12 checks cannot deploy without the operator reading the diff and clicking Approve. The operator sees the fix code, sandbox results, and RAG-retrieved similar incidents. If they reject, the rejection reason is appended to the Fix Writer's context and it retries (up to 3 times). If all 3 retries are rejected, the incident escalates to a human engineer with the full audit trail. No fix ever deploys without a human signature.

---

**"Why Snowflake instead of BigQuery or Redshift?"**

> Three reasons: (1) Hevo Technologies already has a Snowflake partnership — using the same DW avoids integration complexity. (2) Snowflake's serverless compute (warehouse pause/resume) maps well to bursty analytical workloads. (3) Snowflake's credit-based billing makes the Cost Optimizer Agent's impact directly measurable — we can show exact credit savings per optimised query.

---

**"How does the lineage graph actually get populated?"**

> Every Airflow DAG run emits OpenLineage events — job start, dataset read, dataset write, job complete — to the Marquez server via the OpenLineage Python client. Marquez stores these as a directed graph of dataset nodes and job edges. The Lineage page fetches this graph from Marquez's REST API and renders it. The Diagnosis Agent also queries Marquez at incident time — it traverses the upstream lineage from the failing node to identify which source table caused the cascade.

---

**"You use JWT — what are the security risks and how do you mitigate them?"**

> Two main risks: (1) Token theft — mitigated by short expiry (60 minutes) set in `.env`. (2) Weak secret — mitigated by a 256-bit random secret key generated at deployment time. We don't use refresh tokens in the prototype (noted as a constraint) — production would add refresh token rotation. The JWT carries `tenant_id` and `role` claims so multi-tenancy and RBAC enforcement happen at the middleware level without a DB call per request.

---

**"Why full-refresh ETL instead of incremental?"**

> Kleppmann [5] documents the partial-write corruption risk in incremental pipelines — a failed mid-run leaves the destination in an inconsistent state that's hard to reason about. Full-refresh is idempotent: any failed run leaves the destination in its previous complete state. The cost is higher I/O per run, which is acceptable in the prototype. The production path is CDC (Change Data Capture) with Debezium — noted as a Phase 2 enhancement.

---

**"How does the sandbox prevent the fix from affecting production data?"**

> The SandboxNode provisions a **fresh Docker container** for each fix evaluation. The container runs an isolated PostgreSQL instance pre-seeded with a 10% random sample of production data (anonymised). The fix is applied only inside that container. The container is destroyed after the 12-check suite runs — nothing persists. Production data is never touched until the operator clicks Approve and the DeploymentNode merges the GitHub PR.

---

**"What is the Isolation Forest threshold and how did you choose 0.65?"**

> τ = 0.65 was selected empirically on synthetic pipeline telemetry generated from Hevo DAG run logs. Below 0.65, the false positive rate was unacceptably high — the agent would trigger on normal variance. Above 0.65, we'd miss subtle schema fingerprint drifts. The threshold is a configurable parameter in the Monitoring Agent — it can be tuned per pipeline based on observed variance. Post-semester, Experiment 1 will validate this threshold against real production failure data.

---

**"What is Fernet encryption and why use it for connector credentials?"**

> Fernet is a symmetric authenticated encryption scheme from the `cryptography` Python library — AES-128 in CBC mode with HMAC-SHA256 authentication. The authentication tag prevents tampering — an attacker who modifies the ciphertext will get a decryption error, not silently corrupted plaintext. Raw AES-CBC without authentication is unsafe because it's malleable. The encryption key is stored in `.env` and never in the database. Credentials are encrypted before any DB write and decrypted only in memory when a connection test is triggered.

---

## ARCHITECTURE DIAGRAM — VERBAL DESCRIPTION (for whiteboard)

```
┌──────────────────────────────────────────────────────┐
│  PRESENTATION TIER  (Next.js 14, 12 pages)           │
│  Dashboard · Pipelines · AI Analyst · Lineage · ...  │
└────────────────────┬─────────────────────────────────┘
         REST + JSON + JWT (60min expiry)
┌────────────────────▼─────────────────────────────────┐
│  APPLICATION TIER  (FastAPI, 24 endpoints)            │
│  JWT Middleware → Route Handlers → Pydantic Models    │
│  Fernet encryption on connector_configs              │
└────────────────────┬─────────────────────────────────┘
       in-process Python function calls
┌────────────────────▼─────────────────────────────────┐
│  MULTI-AGENT TIER  (LangGraph StateGraph, 10 nodes)  │
│  PipelineHealingState TypedDict (shared, flat)       │
│  Healing Group (1–8) · Analytics Group (9–10)        │
│  Conditional edges: ABORT/FAIL/WARN routing          │
└──────┬──────────┬──────────┬──────────┬──────────────┘
       │          │          │          │
  PostgreSQL  Snowflake  ChromaDB   Marquez
  (relational)(analytics)(vectors)  (lineage)
```

---

*Architecture section: Report pp. 8–12 (Section 3) · PPT Slides 8–9*
