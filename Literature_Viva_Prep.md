# OrchestrAI — Literature Review Viva Prep
**All 11 papers · Gap Analysis · Likely Questions · 30-second answers**

---

## THE 11 PAPERS AT A GLANCE

| Ref | Authors | Paper Title | What it gave OrchestrAI |
|-----|---------|-------------|------------------------|
| [1] | Sculley et al. | Hidden Technical Debt in ML Systems (2015) | OpenLineage monitoring — silent failures made detectable |
| [2] | Amershi et al. | Software Engineering for Machine Learning (2019) | Schema registry + persistent distribution baselines |
| [3] | Zaharia et al. | MLflow (2018) | Single normalised connector API over 6 backends |
| [4] | Breck et al. | TensorFlow Data Validation (2019) | Schema fingerprint + auto fix generation (closed the loop TFDV left open) |
| [5] | Kleppmann | Designing Data-Intensive Applications (2017) | Full-refresh idempotent runs over incremental patching |
| [6] | LangChain AI | LangGraph Framework (2024) | Multi-agent directed graph + PipelineHealingState TypedDict |
| [7] | Lewis et al. | RAG for Knowledge-Intensive NLP Tasks (2020) | ChromaDB incident corpus → Fix Writer Agent grounding |
| [8] | Yao et al. | ReAct: Synergizing Reasoning + Acting (2022) | Scratchpad in Diagnosis + Fix Writer → traceable approval |
| [9] | Guo et al. | Large Language Model Multi-Agent Survey (2024) | Flat shared state — no direct agent-to-agent calls |
| [10] | Chandola et al. | Anomaly Detection Survey (2009) | Isolation Forest selected over LOF and LSTM |
| [11] | Seshia et al. | Human-in-the-Loop CPS (2016) | Approval Gate as contractual graph boundary |

---

## PAPER-BY-PAPER — 30-SECOND ANSWER FOR EACH

---

### [1] Sculley et al. — Hidden Technical Debt (2015)

**What the paper says:**
ML systems accumulate invisible technical debt through hidden coupling between components. A single upstream schema change silently corrupts an entire analytics stack before any alert fires.

**What OrchestrAI took from it:**
Instead of engineers manually inspecting logs, every pipeline run emits structured **OpenLineage events** consumed by the Monitoring Agent in real time. Silent failures become detectable anomalies.

**Key phrase to say:**
> "Sculley showed us the problem — data debt propagates silently. OrchestrAI's response is to make every pipeline run emit observable events so there is no silence."

**Where it appears in your project:** Monitoring Agent, OpenLineage integration, Pipeline Dashboard.

---

### [2] Amershi et al. — Software Engineering for ML at Microsoft (2019)

**What the paper says:**
Large-scale empirical study at Microsoft — most production ML incidents originate in data preparation, not in model selection. Teams with systematic data validation recover faster.

**What OrchestrAI took from it:**
OrchestrAI doesn't do one-off validation. It maintains **persistent schema registry snapshots** and evaluates every new run against stored baselines. Drift is surfaced before any downstream consumer is affected.

**Key phrase to say:**
> "Amershi confirmed that data validation should be continuous, not a one-off check. We embed it into every pipeline run — schema fingerprint comparison, null rate, row count — and trigger the healing loop when it fails."

**Where it appears:** Schema Registry, Data Quality Module, drift detection thresholds.

---

### [3] Zaharia et al. — MLflow (2018)

**What the paper says:**
ML teams waste effort re-implementing lifecycle management across incompatible environments. MLflow solves this with a common API layer.

**What OrchestrAI took from it:**
Applied the same abstraction to **data engineering**: Connector Gallery presents one normalised configuration interface over PostgreSQL, MySQL, Snowflake, BigQuery, Redshift, and S3. Agents interact through one interface regardless of backend.

**Key phrase to say:**
> "MLflow abstracted ML experiments. We applied the same idea to connectors — one interface, any backend. The agent tier doesn't need to know whether it's talking to Snowflake or Postgres."

**Where it appears:** Connector Gallery, `connectors/base.py` connector abstraction.

---

### [4] Breck et al. — TensorFlow Data Validation (2019)

**What the paper says:**
A statistical profile captured at ingestion time — types, null rates, value ranges, categorical vocabularies — provides a specification to mechanically check future data against, eliminating brittle hand-written assertions.

**What OrchestrAI took from it:**
OrchestrAI's schema registry does exactly this. But **it goes further than TFDV**: where TFDV stops at surfacing the deviation, OrchestrAI automatically generates a migration fix and sandbox-tests it.

**Key phrase to say:**
> "Breck's TFDV detects schema drift. We detect it AND fix it. That's the gap TFDV left open — we close it with the Fix Writer Agent."

**Where it appears:** Schema Registry, 12-check sandbox (Check 8: Schema Fingerprint Match), Fix Writer Agent.

---

### [5] Kleppmann — Designing Data-Intensive Applications (2017)

**What the paper says:**
Analyzes correctness and availability trade-offs in data systems. Incremental update models introduce partial-write corruption risk that is hard to reason about.

**What OrchestrAI took from it:**
ETL runs use **full-refresh, idempotent execution** — each run reloads from source. Accepts higher I/O cost in exchange for a simpler correctness argument: any failed run leaves the table in its last complete state.

**Key phrase to say:**
> "Kleppmann documents the distributed systems trade-off. We chose correctness over throughput — idempotent full-refresh runs. A failed pipeline never leaves partial data in the destination."

**Where it appears:** ETL execution engine, pipeline run logic, demo shows full-refresh to Snowflake.

---

### [6] LangChain AI — LangGraph (2024)

**What the paper says:**
LangGraph introduces a programming model for multi-agent AI systems as directed graphs with typed edges and conditional routing. Enables looping, branching, and waiting for external input.

**What OrchestrAI took from it:**
The entire self-healing pipeline is a LangGraph directed cyclic graph: 10 agent nodes, conditional edge routing (ABORT/FAIL/WARN branches), HITL wait state at the Approval Gate.

**Key phrase to say:**
> "LangGraph gave us the graph skeleton. We contributed the domain-specific state schema — PipelineHealingState — and added the RAG retrieval step and Docker sandbox loop that LangGraph's examples don't include."

**Where it appears:** All 10 agent nodes, `PipelineHealingState` TypedDict, conditional edge routing.

---

### [7] Lewis et al. — RAG (2020)

**What the paper says:**
Parametric LLM knowledge degrades over time and can't be updated without retraining. RAG augments generation with a non-parametric retrieval component — fetch relevant documents at inference time.

**What OrchestrAI took from it:**
Applied to a **novel corpus**: every successfully resolved pipeline incident is stored in ChromaDB as a vector embedding. When a new failure occurs, the Fix Writer retrieves top-k semantically similar past incidents for context.

**Key phrase to say:**
> "Lewis demonstrated RAG for factual QA. We applied it to generate executable, deployable code — a harder output space. The fix must be structurally correct, not just factually plausible."

**Where it appears:** ChromaDB, Learning Node, Fix Writer Agent, RAG retrieval in Approval Panel.

---

### [8] Yao et al. — ReAct (2022)

**What the paper says:**
LLM agents perform better and are more auditable when they produce a visible reasoning trace alongside each tool call — "Reasoning + Acting" interleaved.

**What OrchestrAI took from it:**
Diagnosis Agent and Fix Writer Agent maintain a **structured scratchpad** (observation → hypothesis → evidence → action) captured in PipelineHealingState, surfaced in the Human Approval Panel alongside the fix diff.

**Key phrase to say:**
> "ReAct makes agents auditable. In an approval workflow, auditability isn't optional — the operator needs to understand WHY a fix was generated before approving it. Our scratchpad provides exactly that."

**Where it appears:** Diagnosis Agent, Fix Writer Agent scratchpad, Approval Panel left-side reasoning display.

---

### [9] Guo et al. — LLM Multi-Agent Survey (2024)

**What the paper says:**
Survey of multi-agent LLM architectures. Key finding: tightly coupled communication — agents calling each other's methods directly — is a consistent source of fragility. Shared state is safer.

**What OrchestrAI took from it:**
Agents coordinate **only through the flat, serialisable PipelineHealingState**. No agent calls another agent's method directly. Each node reads only its designated fields and writes only its designated outputs.

**Key phrase to say:**
> "Guo's survey showed that direct agent-to-agent calls create fragile systems. Our architecture: zero direct calls. Every agent reads from and writes to the shared TypedDict only."

**Where it appears:** PipelineHealingState architecture, agent node design pattern throughout.

---

### [10] Chandola et al. — Anomaly Detection Survey (2009)

**What the paper says:**
Comprehensive taxonomy of anomaly detection by type and algorithm family. Reviews LOF, LSTM autoencoders, Isolation Forest, statistical process control.

**What OrchestrAI took from it (and WHY each alternative was rejected):**
- **LOF** → rejected: O(n²) worst-case complexity, too slow across many concurrent pipeline runs
- **LSTM autoencoders** → rejected: requires long historical sequences; newly registered pipelines have < 30 runs
- **Statistical process control** → rejected: univariate only; can't capture multivariate dependencies between row count, execution time, and null rate
- **Isolation Forest** → selected: sub-linear average complexity, robust on small samples, native multivariate support, no distributional assumptions

**Key phrase to say:**
> "Chandola's survey gave me the framework to systematically compare options. Isolation Forest won because it handles multivariate telemetry, works on small samples, and has sub-linear complexity."

**Where it appears:** Monitoring Agent, Anomaly Detector, `agents/healing/monitoring_agent.py`.

---

### [11] Seshia et al. — Human-in-the-Loop CPS (2016)

**What the paper says:**
For autonomous systems in high-stakes domains, correctness requires structured human oversight at well-defined decision boundaries. Automation should increase human authority over consequential actions, not erode it.

**What OrchestrAI took from it:**
The Approval Gate is not a UI affordance — it is a **contractual boundary in the agent graph** that cannot be bypassed. Every proposed fix must pass through it before deployment.

**Key phrase to say:**
> "Seshia's work is why the Approval Gate exists. In a system that writes and deploys code to production databases, autonomy without oversight would be irresponsible engineering. The gate is a formal contract, not a button."

**Where it appears:** ApprovalGateNode, HITL wait state in LangGraph, Approval Panel in UI.

---

## GAP ANALYSIS — COMPARISON TABLE EXPLAINED

| Tool | Score | What it does | What it's MISSING |
|------|-------|--------------|-------------------|
| **Monte Carlo Data** | 6/10 | Anomaly detection, lineage, alerting | No auto fix, no sandbox, no HITL gate, no NL-SQL |
| **Great Expectations** | 4/10 | Data validation rules, test suites | No lineage, no fix generation, no LLM, no sandbox |
| **Datafold** | 4/10 | Data diff, lineage explorer, column profiling | No anomaly detection, no fix, no NL-SQL, no sandbox |
| **dbt Cloud** | 5/10 | Transformation orchestration, testing, lineage | No anomaly detection, no auto-healing, no NL-SQL |
| **OrchestrAI** | **10/10** | All 10 capabilities | — |

**The 3 capabilities NO other tool has:**
1. Autonomous fix generation (AI writes the repair code)
2. Sandboxed fix testing (Docker 12-check harness before any human sees it)
3. RAG-based continuous learning (system improves with every incident)

---

## LIKELY INVIGILATOR QUESTIONS ON LITERATURE

---

**"Why did you choose these 11 papers specifically?"**

> Each paper maps to a specific architectural decision. [1] and [2] established the problem space. [3] and [4] shaped the connector and validation design. [5] resolved an ETL correctness trade-off. [6]–[9] directly drove the agent architecture. [10] selected the anomaly algorithm. [11] justified the HITL gate. There are no decorative references — every paper is implemented.

---

**"How is your work different from what already exists in the literature?"**

> No existing paper or tool combines autonomous fix generation, sandboxed testing, lineage-aware diagnosis, RAG-based learning, and a human-in-the-loop approval gate in a single operational platform. Each of our references solves one piece. We synthesise all of them.

---

**"[4] Breck et al. — TFDV already does schema validation. What did you add?"**

> TFDV detects and reports schema drift. It stops there. OrchestrAI takes the detection output and triggers the Fix Writer Agent to generate a targeted migration script, test it in Docker, and route it through human approval. We closed the detection-to-remediation loop that TFDV leaves open.

---

**"[10] Why not LOF or LSTM for anomaly detection?"**

> LOF is O(n²) — too slow when monitoring dozens of concurrent pipeline runs. LSTM autoencoders need 30+ runs of history; a newly registered pipeline doesn't have that. Isolation Forest is O(n log n), works on small samples, handles multivariate features (row count + null rate + execution time together), and needs no labelled data. All three rejections are documented in Chandola et al.'s survey.

---

**"[11] You say it's autonomous, but there's a human. Isn't that a contradiction?"**

> No — and Seshia et al. [11] explains why. Autonomous means the system diagnoses root cause and generates the fix without human effort. The human's role shifts from detective + developer to approver. In a system that deploys code to production databases, removing the approval gate would be irresponsible. Seshia frames HITL not as a limitation but as the correct design for high-stakes autonomous systems.

---

**"What is the limitation of RAG [7] in your context?"**

> Two limitations. First, the retrieval corpus is empty at deployment — the system has no past incidents to learn from until it resolves its first failures. This cold-start problem means early fixes rely entirely on the LLM's parametric knowledge. Second, RAG retrieval quality depends on the quality of incident descriptions stored — a poorly written root-cause summary will return poor matches. We mitigate both by pre-seeding ChromaDB with synthetic incident examples at initialisation.

---

**"Why Kleppmann [5] — that's a textbook, not a paper?"**

> The DSR methodology permits any credible source that informed design decisions — textbooks, framework documentation, and industry papers are all valid. Kleppmann's book is the standard reference for data system design trade-offs. It directly informed a concrete architectural decision: full-refresh over incremental patching. The design choice is implemented, justified, and citable.

---

**"How do you know your feature comparison table [Table 1] is accurate?"**

> The comparison was compiled from official documentation for each tool as of May 2025 — Monte Carlo's product docs, Great Expectations' feature matrix, Datafold's public documentation, and dbt Cloud's capability page. The comparison table is dated and cited. No tool's documentation claimed autonomous fix generation or sandboxed testing capabilities.

---

## THREE SENTENCES TO OPEN IF ASKED ABOUT LITERATURE

> "Our literature review covers 11 works across four areas — technical debt and data reliability [1,2,5], machine learning infrastructure [3,4], LLM and multi-agent architectures [6,7,8,9,10], and human-machine teaming [11]. Each reference maps directly to a design decision in the platform. The key synthesis is that no prior work combines all these components — the gap analysis in Table 1 shows that the closest competitor covers only 6 of our 10 capabilities."

---

*Literature section: Report pp. 4–12 · PPT Slides 5–6*
