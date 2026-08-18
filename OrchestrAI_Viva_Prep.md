# OrchestrAI — Mid-Semester Viva Preparation
**Parthiv Patel | 2024AA05129 | M.Tech AI & ML | BITS ZG628T**

---

## CHEAT SHEET — Numbers You Must Know Cold

| What | Number |
|------|--------|
| Overall completion | **72%** |
| Agent nodes (LangGraph) | **10** |
| REST API endpoints | **24** (all passing) |
| Frontend pages | **12** |
| Source files | **42** |
| Bugs resolved | **19** (3 root-cause categories) |
| Docker sandbox checks | **12** (4 ABORT · 5 FAIL · 3 WARN) |
| Research objectives | **8** |
| Papers reviewed | **11** |
| Planned experiments | **3** |
| Development sprints | **8** |
| Industry partner | Hevo Technologies India Pvt. Ltd., Bengaluru |
| Experiment 1 target | >50% MTTR reduction |
| Experiment 2 target | >65% NL-SQL exact match (Spider v1.0, ~1,034 Qs) |
| Experiment 3 target | >30% Snowflake query cost savings |
| Baseline tools beaten | Monte Carlo (6/10), Great Expectations (4/10), Datafold (4/10), dbt Cloud (5/10) |
| OrchestrAI features | **10/10** — only platform with all capabilities |

---

## 20 PANEL QUESTIONS WITH MODEL ANSWERS

### SECTION A — Core Concept

---

**Q1. What exactly does "self-healing" mean in your project? Can you give a concrete example?**

> Self-healing means the platform detects a pipeline failure, diagnoses the root cause, writes a code fix, tests it in a sandboxed Docker environment, gets human approval, deploys it, and then learns from the outcome — all without a human debugging the root cause manually.
>
> Concrete example: a `payments_raw` table has a column renamed from `amount_usd` to `amount`. The Anomaly Detector flags the schema drift. The Diagnosis Agent traces the lineage: 3 downstream dbt models are broken. The Fix Writer Agent retrieves a similar past incident from ChromaDB (RAG) and generates an ALTER TABLE migration. The sandbox runs all 12 checks — passes. The Approval Gate presents the diff to the operator. Operator clicks Approve. The fix deploys. The Learning Node stores this incident for next time. MTTR: 4 minutes instead of 2 hours.

---

**Q2. Why did you choose LangGraph over AutoGen or CrewAI?**

> Three reasons. First, LangGraph gives explicit state management through a typed `PipelineHealingState` dictionary — every agent reads from and writes to this shared state, so there are no hidden side channels. Second, its conditional edge routing lets me wire in the ABORT/FAIL/WARN sandbox logic cleanly — I can branch the graph based on severity. Third, LangGraph is part of the LangChain ecosystem, which already had integrations I needed: ChromaDB for RAG, OpenAI/Groq for LLM calls. AutoGen uses conversational multi-agent patterns which are harder to control for a deterministic pipeline workflow; CrewAI is higher abstraction but less flexible for custom state graphs.

---

**Q3. What is `PipelineHealingState` and why is it important?**

> It's a Python `TypedDict` — a shared data structure that flows through the entire LangGraph graph. It contains fields like `pipeline_id`, `failure_type`, `root_cause`, `proposed_fix`, `sandbox_results`, `approval_status`, and `learning_feedback`. Every agent only reads and writes to this state — no agent calls another agent directly. This is important because it makes the system testable (you can unit-test each agent node in isolation), auditable (the full state at each step is inspectable), and safe (no agent can take an action outside its defined state mutations).

---

**Q4. What are your 10 agents and what does each do?**

> 1. **Ingestion Monitor** — polls pipeline run logs for failures
> 2. **Anomaly Detector** — Isolation Forest on row counts, null rates, schema fingerprints
> 3. **Schema Validator** — compares current schema against registry fingerprint
> 4. **Diagnosis Agent** — ReAct reasoning to trace lineage and identify root cause
> 5. **Fix Writer Agent** — RAG-augmented LLM that generates SQL/dbt fix
> 6. **Sandbox Executor** — runs the fix in Docker, executes all 12 checks
> 7. **Approval Gate Node** — pauses graph, presents diff + results to human operator
> 8. **Deployment Agent** — applies approved fix to production after gate passes
> 9. **Learning Node** — stores incident + fix + outcome in ChromaDB for future RAG retrieval
> 10. **Cost Optimizer Agent** — separate path: detects anti-patterns (missing partitions, cross joins), rewrites SQL, estimates credit savings

---

### SECTION B — Technical Depth

---

**Q5. Why Isolation Forest for anomaly detection instead of LSTM or LOF?**

> Two reasons from the literature ([10] Chandola et al.). LOF has O(n²) time complexity — too slow for streaming pipeline telemetry at Hevo's scale. LSTM requires a significant history of labelled sequences to train, which we don't have for rare pipeline failure patterns. Isolation Forest is O(n log n), requires no labelled data (unsupervised), and is robust to high-dimensional mixed telemetry (row counts + null rates + execution time together). It isolates anomalies by randomly partitioning feature space — anomalous points are isolated in fewer splits.

---

**Q6. How does the RAG work for fix retrieval?**

> When the Fix Writer Agent is invoked, it takes the Diagnosis Agent's root cause description and embeds it using an OpenAI embedding model. It queries ChromaDB with this embedding, retrieves the top-3 most similar past incidents by cosine similarity. These past incidents — including the original failure, the fix that was applied, and the outcome — are prepended as context in the LLM prompt. This grounds the fix in proven solutions rather than hallucinated code. The Learning Node closes the loop: after every successful deployment, it stores the new incident-fix pair back into ChromaDB, so the system compounds its knowledge over time.

---

**Q7. What are the 12 sandbox checks? What's the difference between ABORT, FAIL, and WARN?**

> The 12 checks run inside a Docker container against a sample of the data before any fix touches production.
>
> **ABORT (4 checks):** Row Count Minimum, Primary Key Uniqueness, Data Type Consistency, Execution Time Limit. These are hard stops — if any fail, the fix is rejected immediately and escalated to an operator. No further execution.
>
> **FAIL (5 checks):** Null Rate per Column, New Null Columns, Foreign Key Integrity, Schema Fingerprint Match, No All-Null Columns. These are configurable — in strict mode they stop; in permissive mode they log and continue.
>
> **WARN (3 checks):** Row Count Stability, Numeric Mean Drift, Categorical Value Set. These log and always continue — they signal drift but don't block deployment.

---

**Q8. How does NL-to-SQL work technically in the AI Analyst?**

> The user types a plain-English question. The system sends it to the LLM with the database schema injected into the system prompt. The LLM generates SQL. Before execution, the SQL goes through a validation step — it's parsed with `sqlparse` to check for syntax errors and dangerous patterns (DROP, TRUNCATE, unbounded scans). If validation passes, the SQL runs against the data warehouse. The result is returned to the UI as both a data table and rendered as a bar/line chart via Recharts. A second LLM call then generates a plain-English AI Insight summarising the result. In Phase 2 I'm benchmarking this against Spider v1.0 (exact match metric, ~1,034 questions).

---

**Q9. What security measures does the platform have?**

> Three layers. First, JWT authentication on every `/api/*` endpoint — every request carries a signed token, validated by middleware before the handler runs. Second, RBAC — roles (admin, analyst, viewer) with permission checks per endpoint. Third, Fernet symmetric encryption for all connector credentials stored in the database — the raw credentials are never stored in plaintext; they're encrypted at write time and decrypted only in memory when needed. I also implemented a PII detection scanner that tags columns containing personal data in the data catalog.

---

**Q10. How does OpenLineage / Marquez fit into the architecture?**

> OpenLineage is an open standard for capturing data lineage events. Every time a pipeline runs, the backend emits an OpenLineage event (job start, dataset read, dataset write, job complete) to Marquez — an open-source lineage server. This populates the Lineage page in the UI, where I render a directed graph of dataset → transformation → dataset relationships. The Diagnosis Agent also queries Marquez to trace which downstream models are broken when an upstream schema change is detected — that's how it identifies root cause and impact scope.

---

### SECTION C — Research & Methodology

---

**Q11. Why Design Science Research (DSR) as your methodology?**

> Because OrchestrAI's value is inseparable from its artefact. DSR, as formalised by Hevner et al. (2004), is the right methodology when you're both building and evaluating an IT artefact in a real organisational context. A purely empirical study would only evaluate the system — it wouldn't account for how design decisions were derived from the problem. DSR's 6 activities (Problem ID → Objectives → Design → Demonstration → Evaluation → Communication) map directly to my project lifecycle: I identified the problem at Hevo, defined measurable objectives, built the system over 8 sprints, demonstrated it, and will evaluate it through 3 pre-registered experiments.

---

**Q12. Your 3 experiments — how are they statistically rigorous?**

> All three are pre-registered — success criteria were defined before data collection, preventing p-hacking.
>
> **Experiment 1 (MTTR):** 20 injected failures × 5 failure types × 5 repetitions = 100 test runs. Paired t-test at α=0.05 comparing OrchestrAI MTTR vs. rule-based baseline and no-healing baseline. The pairing controls for failure-type variance.
>
> **Experiment 2 (NL-SQL):** Standard Spider v1.0 evaluation script — exact match and execution match metrics — on the full test set (~1,034 questions). This is a public benchmark, so results are directly comparable to published work.
>
> **Experiment 3 (Cost):** 30 representative Snowflake queries from Hevo's history. I measure credit usage before and after Cost Optimizer Agent rewrite using Snowflake's query history API. Percentage reduction reported with 95% CI.

---

**Q13. What is your research gap? Why doesn't Monte Carlo or Great Expectations solve the problem?**

> Monte Carlo (6/10 features), Great Expectations (4/10), Datafold (4/10) — none of them close the full loop. They detect problems and alert humans. No existing tool autonomously writes a fix, tests it in a sandbox, routes it through a human gate, deploys it, and learns from it. That's the gap: the industry has excellent *detection* tools but zero *autonomous remediation* tools with a formal human-in-the-loop boundary. OrchestrAI is the first platform to combine all 10 capabilities including auto-fix, sandboxed testing, HITL approval, and RAG-based continuous learning.

---

### SECTION D — Tough / Critical Questions

---

**Q14. Is this actually deployed at Hevo or is it just a prototype?**

> The platform is running locally and has been smoke-tested against mock data that is structurally identical to Hevo's production schema. All 24 endpoints return correct responses across 5 consecutive clean runs. The PostgreSQL live database integration is Phase 1 of the post mid-semester roadmap — we're replacing the demo-data fallback with Alembic migrations against a real instance. The reason it isn't in production yet is that any system that autonomously modifies production pipelines needs to complete the formal evaluation experiments first — that's the correct scientific and engineering sequence.

---

**Q15. What if the Fix Writer Agent generates a wrong fix that passes all 12 sandbox checks?**

> That's exactly why the Human Approval Gate is a contractual graph boundary, not a courtesy step. Even if all 12 checks pass, no fix deploys without a human reading the diff and clicking Approve. The operator sees: the proposed SQL, the sandbox results, the RAG-retrieved similar incidents, and the confidence score. The HITL gate is grounded in Seshia et al.'s [11] formal verification work — human oversight as a mandatory contractual checkpoint, not optional. Additionally, the Learning Node captures outcomes: if a fix later causes issues, that negative outcome is stored and ChromaDB retrieval deprioritises similar fixes in future.

---

**Q16. Why did you choose Hevner 2004 specifically — isn't there newer DSR literature?**

> Hevner 2004 remains the canonical DSR framework in IS research. It's the most-cited methodology paper for IT artefact research and is accepted by BITS for M.Tech dissertations. More recent DSR extensions (e.g., Peffers 2007 DSRM) are refinements that don't change the core philosophical basis. I reference both in the report but use Hevner's 6-activity structure as my primary framework because it explicitly includes the "Communication" activity — which is this viva and the final dissertation.

---

**Q17. What happens if Experiment 1 fails — MTTR doesn't improve by 50%?**

> The dissertation would still be a valid contribution — a null result is a result. I'd report the actual improvement achieved, analyse *why* the target wasn't met (e.g., LLM latency in fix generation, sandbox overhead), and propose engineering optimisations. The scientific contribution isn't just the MTTR number — it's the demonstration that a multi-agent self-healing architecture with a formal HITL gate is feasible at this scale, and the quantification of where bottlenecks lie. I've also built in a contingency: if live Hevo data isn't available in time, the experiments run against the 20-failure synthetic harness I've already built.

---

**Q18. What is your industry supervisor's role and feedback so far?**

> My industry supervisor at Hevo Technologies has provided access to the technical architecture of their pipeline infrastructure, defined the operational pain points (schema drift, cost overruns, dbt debt), and validated that the 3 problem categories in Chapter 1 are real operational issues with measurable business impact. The mid-semester deliverable — the working platform with all 24 endpoints — has been reviewed at the sprint level. Post mid-semester, the live database integration will be done on a staging environment at Hevo before any production use.

---

**Q19. How is OrchestrAI different from just using ChatGPT to fix SQL?**

> Three fundamental differences. First, ChatGPT has no access to your pipeline state, lineage graph, schema registry, or run history — it can't know what broke or why. OrchestrAI's agents have structured access to all of these via PipelineHealingState. Second, ChatGPT generates text — OrchestrAI's Fix Writer generates executable SQL that is *tested in a Docker sandbox* before it's ever shown to a human. Third, the RAG system grounds fixes in your organisation's own incident history — it learns what has worked in your specific environment, not generic SQL patterns. ChatGPT is a component (the LLM backbone), not a solution.

---

**Q20. You said "autonomous" — but there's a human in the loop. Isn't that a contradiction?**

> Not at all — and this is a deliberate design choice grounded in AI safety literature ([11] Seshia et al.). "Autonomous" refers to the diagnosis and fix-generation being fully automated — no human needs to debug, identify root cause, or write code. The human's role is reduced from *detective + developer* to *approver*. This is the correct architecture for a system that touches production data infrastructure. Full autonomy without oversight in this domain would be irresponsible engineering. The HITL gate is a strength, not a limitation — it's what makes the system deployable in a regulated enterprise context.

---

## QUICK TIPS FOR THE VIVA

- **Lead with the demo in your head.** The panel will ask "show me how it works" — have the 7-step healing loop rehearsed as a story: *detect → diagnose → fix → sandbox → approve → deploy → learn.*
- **Don't get defensive about Post Mid items.** Say "that's Phase 2 — here's specifically what I've built and what remains." Confidence, not apology.
- **If asked something you don't know:** "That's a good question — I haven't benchmarked that specifically, but my hypothesis is X because of Y." Never bluff.
- **Anchor every answer in a number.** Panels respect specificity. "10 agents", "24 endpoints", "12 checks", "72% complete."
- **15 minutes = ~2 min per section.** Don't over-explain slide 1. Save depth for slides 8–13.

---

*Prepared June 2026 — OrchestrAI Mid-Semester Viva*
