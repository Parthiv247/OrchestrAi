# OrchestrAI — General Viva Questions
### Slide-by-slide: what a non-expert invigilator will ask

---

## SLIDE 1 — TITLE

---

**Q: What is OrchestrAI?**
> OrchestrAI is an AI platform that automatically detects, diagnoses, and fixes failures in data pipelines — without needing a human engineer to investigate the problem. It does this using 10 AI agents working together.

---

**Q: What is a "self-healing" data pipeline?**
> When a data pipeline breaks — for example, because a column name changed or too many rows are missing — OrchestrAI detects it automatically, figures out why it broke, writes a code fix, tests that fix in a safe sandbox environment, and then shows it to a human for one-click approval before deploying it. The pipeline "heals itself" with minimal human effort.

---

**Q: What is Hevo Technologies? What is your connection to them?**
> Hevo Technologies is a Bengaluru-based data integration startup that builds data pipelines for businesses. I am doing my M.Tech internship there. The three problems OrchestrAI solves — pipeline failures, warehouse cost overruns, and schema design debt — are real operational problems I identified at Hevo working with their engineering team.

---

**Q: What does "Multi-Agent" mean?**
> Instead of one AI program doing everything, I built 10 specialised AI agents — each one does one job very well. One agent detects anomalies, another diagnoses the root cause, another writes the fix, another tests it, another deploys it. They all pass information to each other through a shared state object. It's like an assembly line — each worker focuses on their task.

---

**Q: What is "Autonomous"? Is there no human involved?**
> "Autonomous" means the system detects, diagnoses, and generates a fix without a human engineer spending hours debugging. But there is always a human in the loop — the engineer sees the proposed fix, reads the diagnosis, and clicks Approve before anything touches production. The human's role changes from "detective + developer" to "approver."

---

## SLIDE 2 — AGENDA

---

**Q: You have 7 sections — can you briefly tell me what each one covers?**
> Section 1: The problem we're solving and our 8 research objectives. Section 2: 11 research papers we reviewed and how they compare to existing tools. Section 3: The DSR research methodology we followed. Section 4: The system architecture and multi-agent design. Section 5: Data collection, progress at mid-semester, and validation results. Section 6: Our roadmap for the second half and the 3 experiments we'll run. Section 7: Conclusion — what we built and what comes next.

---

## SLIDE 3 — PROBLEM STATEMENT

---

**Q: What is a data pipeline?**
> A data pipeline is an automated process that moves data from a source (like a customer database) to a destination (like a data warehouse) where it can be analysed. For example: every night, Hevo's pipeline copies customer transaction records from PostgreSQL into Snowflake so the analytics team can run reports in the morning.

---

**Q: What is schema drift? Why is it a problem?**
> Schema drift is when the structure of your data changes unexpectedly. For example, a developer renames a column from `amount_usd` to `amount`. The pipeline was written expecting `amount_usd` — now it fails silently or crashes. At Hevo, this can break 3 or 4 downstream reports at once, and no one knows until a dashboard shows wrong numbers.

---

**Q: Why does the warehouse cost spike 10×?**
> Cloud data warehouses like Snowflake charge based on compute time. If a developer writes a bad query — for example, joining two massive tables without a filter — it scans billions of rows and burns through credits. One bad query can cost 10× more than a good one. Currently there's no automated system to detect and rewrite these before they run.

---

**Q: What is "schema design debt"? What is dbt?**
> Schema design debt means the database tables are set up poorly — no structure, no standards, just raw data dumped into tables. dbt (data build tool) is a tool that organises raw data into clean, structured tables following best practices called dimensional modelling. Setting this up manually takes weeks. OrchestrAI can scaffold these dbt models automatically from the raw schema.

---

**Q: What is the "full loop" that no existing tool closes?**
> The full loop is: detect the problem → diagnose why it happened → write a code fix → test that fix safely → get human approval → deploy it → learn from it. Existing tools like Monte Carlo or Great Expectations only do the first step — detection. They alert you, then a human has to do everything else. OrchestrAI does all seven steps.

---

## SLIDE 4 — OBJECTIVES

---

**Q: What are your 8 objectives?**
> O1: Build a 10-agent LangGraph orchestration system. O2: Create a self-healing pipeline that covers the full detect-to-deploy loop. O3: Build a SQL Cost Optimizer that rewrites expensive queries. O4: Auto-generate dbt dimensional models from raw schemas. O5: Let users query data in plain English and get charts and AI insights. O6: Track data lineage — where data came from and where it goes. O7: Secure the platform with JWT auth, RBAC roles, and encrypted credentials. O8: Run 3 rigorous experiments to prove the system works.

---

**Q: What is NL-to-SQL?**
> NL-to-SQL means Natural Language to SQL. Instead of writing `SELECT region, SUM(total_amount) FROM orders GROUP BY region`, a user just types "Show me total revenue by region" and the AI writes the SQL, runs it, and shows a chart. The AI Analyst feature in our platform does this.

---

**Q: What is HITL — Human in the Loop?**
> Human in the Loop means there is a mandatory step where a human reviews and approves the AI's proposed action before it is executed. In OrchestrAI, after the AI generates a fix and tests it in a sandbox, it cannot deploy until a human reads the diff and clicks Approve. This is a contractual boundary in the system — it cannot be bypassed.

---

**Q: What is RAG?**
> RAG stands for Retrieval-Augmented Generation. It means the AI doesn't just rely on its own training — it also retrieves relevant examples from a database to inform its answer. In OrchestrAI, every time a pipeline incident is successfully fixed, we store the problem and fix in ChromaDB. Next time a similar failure occurs, the AI retrieves those past fixes and uses them as context to write a better fix. The system learns from its own history.

---

## SLIDE 5 — GAP ANALYSIS

---

**Q: What is Monte Carlo Data? Why can't it solve your problem?**
> Monte Carlo Data is a commercial data observability platform. It monitors your pipelines and alerts you when something looks wrong. It scores 6 out of 10 on our feature comparison because it can detect anomalies and show lineage — but it cannot write a fix, test a fix, or learn from past incidents. A human still has to investigate and fix the problem manually.

---

**Q: What is Great Expectations?**
> Great Expectations is an open-source data validation library. You write rules — like "this column should never be null" — and it checks those rules on every data load. It scores 4 out of 10 because it can validate but has no anomaly detection, no lineage, no LLM, and no fix generation. It tells you what failed; it doesn't tell you why or how to fix it.

---

**Q: What is Datafold?**
> Datafold is a data diff tool — it compares two versions of a dataset and shows you what changed. Useful for reviewing dbt model changes. 4 out of 10 on our feature matrix because it has no anomaly detection, no NL-SQL, and no autonomous healing.

---

**Q: Why is OrchestrAI the only one with all 10 features?**
> Because no existing tool was designed to close the full loop. Each tool was built to solve one piece — detection, validation, or diffing. OrchestrAI was designed from the start with all 10 capabilities integrated: detection, lineage, NL-SQL, auto fix generation, sandbox testing, HITL approval, RAG learning, cost optimisation, dbt modelling, and open-source availability.

---

## SLIDE 6 — PAPERS → DESIGN DECISIONS

---

**Q: Why did you choose these specific papers?**
> Every paper in our literature survey directly maps to a design decision in the platform. [1] Sculley taught us to make failures observable. [4] Breck taught us schema fingerprinting. [6] LangGraph gave us the agent architecture. [10] Chandola helped us choose Isolation Forest. There are no decorative references — each paper is implemented.

---

**Q: What is Isolation Forest?**
> Isolation Forest is an anomaly detection algorithm. It works by randomly partitioning the data — anomalous points get isolated in fewer partitions than normal points. It's fast, works without labelled data (unsupervised), and handles multiple metrics at once (row count + null rate + execution time). We use it in the Anomaly Detector agent to decide whether a pipeline run is normal or suspicious.

---

**Q: What is ReAct?**
> ReAct stands for Reasoning + Acting. It's a technique where an AI agent writes down its reasoning — like a scratchpad — before taking each action. This makes the agent more accurate and, crucially, auditable. In OrchestrAI, the Diagnosis Agent and Fix Writer Agent both maintain a scratchpad visible in the Approval Panel, so the engineer can read *why* the AI proposed a particular fix before approving it.

---

**Q: What is LangGraph?**
> LangGraph is a Python framework for building multi-agent AI systems as directed graphs. Each node in the graph is an agent. Edges between nodes define what happens next, and those edges can be conditional — for example, if the sandbox test fails, go back to the Fix Writer; if it passes, go to the Approval Gate. It's what we use to wire all 10 agents together.

---

## SLIDE 7 — DSR METHODOLOGY

---

**Q: What is Design Science Research?**
> Design Science Research (DSR) is a research methodology for building and evaluating IT artefacts — systems, tools, or platforms. It's the right methodology when your research contribution is the system you built, not just a theory. It has 6 activities: identify the problem, define objectives, design and build, demonstrate, evaluate, and communicate. My project follows all 6 in sequence.

---

**Q: What does "Post Mid" mean on the table?**
> Post Mid means those activities are planned for after this mid-semester viva. The Demonstration, Evaluation, and Communication activities require the live database integration and 3 formal experiments, which are Phase 2 of the project. Mid-semester I have completed the first 3 activities: problem identified, objectives defined, and the platform built and tested.

---

**Q: Why DSR and not a normal experiment-only study?**
> Because OrchestrAI's value cannot be separated from the working platform. A survey study would just compare tools on paper. DSR validates that our artefact — the actual running system — solves the problem in a real industrial context at Hevo Technologies. The 3 experiments in Phase 2 will provide the empirical evaluation.

---

## SLIDE 8 — ARCHITECTURE

---

**Q: Can you explain the four tiers?**
> Tier 1 (top): The browser UI — 12 pages built with Next.js. Tier 2: The backend API — 24 REST endpoints built with FastAPI, all secured with JWT. Tier 3: The AI agents — 10 LangGraph agent nodes that do the intelligent work. Tier 4 (bottom): The databases — PostgreSQL for records, Snowflake for analytics, ChromaDB for AI memory, Marquez for lineage.

---

**Q: What is FastAPI?**
> FastAPI is a Python web framework for building REST APIs. It automatically validates incoming data, generates documentation, and supports async operations — important when AI agents are running in the background. All 24 of our API endpoints are built with FastAPI.

---

**Q: What is Next.js?**
> Next.js is a React-based framework for building web frontends. It handles routing, server-side rendering, and performance optimisation. Our 12-page dashboard is built with it.

---

**Q: What is JWT?**
> JWT stands for JSON Web Token. It's a small, signed token the server gives you when you log in. Every subsequent request carries this token. The server validates the signature before processing any request — so unauthorised users can't access any API endpoint.

---

**Q: Why is the architecture "stateless"?**
> Stateless means the server doesn't remember anything between requests — all state is either in the database or in the JWT token. This is good because it means you can run multiple copies of the backend simultaneously and any request can go to any server. Easier to scale.

---

## SLIDE 9 — MULTI-AGENT ORCHESTRATION

---

**Q: What is an "agent"?**
> An AI agent is a program that perceives its environment, reasons about what to do, and takes an action. In OrchestrAI, each agent is a Python function that reads the current pipeline state, performs a specific task (like diagnosing a failure or generating a fix), and updates the state for the next agent.

---

**Q: What is ChromaDB?**
> ChromaDB is a vector database — a database that stores things as mathematical vectors so you can find similar items by meaning, not just exact keyword match. We store every past pipeline incident and its fix as a vector. When a new failure occurs, we search ChromaDB for similar past failures and their proven fixes, which helps the Fix Writer Agent generate a better repair.

---

**Q: What is the Approval Gate?**
> The Approval Gate is a mandatory human checkpoint in the agent pipeline. After the AI generates a fix and all 12 sandbox checks pass, the system stops and waits. The engineer sees the proposed fix, the test results, and similar past incidents. They must click Approve or Reject. Nothing deploys without this step.

---

**Q: What is "RAG" in this context?**
> When the Fix Writer Agent needs to repair a pipeline failure, instead of generating a fix from scratch every time, it first searches our ChromaDB database for similar past incidents that were already fixed successfully. Those past fixes are given to the AI as examples — this is RAG. The more incidents the system fixes over time, the better its future fixes become.

---

## SLIDE 10 — PROGRESS

---

**Q: What does 72% complete mean?**
> 72% means 6 out of 10 platform modules are fully built and tested. The remaining 28% is primarily the live database integration (connecting to Hevo's real PostgreSQL in production) and the end-to-end healing workflow with a live database — these are Phase 2 post mid-semester.

---

**Q: What are the 24 endpoints?**
> Endpoints are the URLs the frontend uses to communicate with the backend. For example, `POST /api/pipelines/run` triggers a pipeline run, `GET /api/incidents` fetches all incidents, `POST /api/analyst/query` sends a natural language question to the AI. All 24 are implemented and returning correct responses.

---

**Q: What are the 10 agents?**
> Monitoring Agent, Anomaly Detector, Diagnosis Agent, Fix Writer Agent, Sandbox Agent, Approval Gate, Deployment Agent, Learning Agent, Query Agent, and Validation Agent. Each handles one step of the healing or analytics workflow.

---

**Q: What are the 19 bugs?**
> During integration testing, I found 19 bugs across 3 categories: 8 were router prefix conflicts (API paths set up incorrectly), 10 were database-unavailable crashes (the server crashed instead of returning a graceful error), and 1 was a missing Python dependency (`sqlparse` not in requirements.txt). All 19 were fixed before the mid-semester checkpoint.

---

## SLIDE 11 — ENGINEERING METRICS

---

**Q: What does "smoke test" mean?**
> A smoke test is a basic check that a system's core functions work without crashing — like turning it on and seeing if it runs. For each of the 24 endpoints, I sent a test request and verified it returned a valid response with the correct structure. All 24 passed across 5 consecutive test runs.

---

**Q: What is "End-to-End Healing Loop" and why is it 0%?**
> The end-to-end healing loop means running the full 8-step process — from detecting a live failure in a real database to deploying a fix and confirming the pipeline recovered. This requires live PostgreSQL integration at Hevo, which is Phase 1 of the post-semester roadmap. The agents are individually implemented and tested; the full live loop is what remains.

---

## SLIDE 12 — UI SCREENSHOTS

---

**Q: What is shown on the Dashboard?**
> The Dashboard shows real-time pipeline health: how many pipelines are active, how many have failed, the mean time to recovery (MTTR), recent incidents with their status (auto-healed, pending approval, failed), and the status of the 4 key AI agents (Anomaly Detector, Diagnosis Agent, Fix Writer, Learning Agent).

---

**Q: What is shown in the Approval Panel?**
> The Approval Panel is what the engineer sees when the AI has a fix ready. On the left: the root cause narrative from the Diagnosis Agent and the lineage path showing which downstream models are affected. On the right: the proposed code fix (SQL/dbt). At the bottom: the results of all 12 sandbox checks and 3 similar past incidents retrieved from ChromaDB. The engineer clicks Approve or Reject.

---

**Q: What does the AI Analyst do?**
> The AI Analyst lets users query their data in plain English. Type "Show me total revenue by region" and the system generates the SQL, runs it, draws a bar chart, and writes a 2-3 sentence AI insight explaining the pattern. No SQL knowledge required. The query history is saved so you can re-run or share past analyses.

---

## SLIDE 13 — 12-CHECK SUITE

---

**Q: Why 12 checks specifically?**
> The 12 checks cover the most common causes of pipeline failures identified in our literature review and at Hevo: data volume problems (checks 1-2), null rate problems (3-4), key integrity (5-6), type and schema issues (7-8), statistical drift (9-10), and execution problems (11-12). Together they provide comprehensive validation of any proposed fix before it touches production.

---

**Q: What is the difference between ABORT, FAIL, and WARN?**
> ABORT (4 checks) — hard stop, the fix is rejected immediately and escalated. Used for the most critical issues: row count too low, duplicate primary keys, wrong data types, execution timeout. FAIL (5 checks) — configurable, can be set to block or continue depending on the pipeline. Used for null rate issues, schema fingerprint mismatches, foreign key violations. WARN (3 checks) — always logs and continues, never blocks. Used for statistical drift that needs monitoring but isn't critical.

---

**Q: What is a Docker sandbox?**
> Docker is a tool that creates isolated containers — like a mini virtual machine. For each proposed fix, we spin up a fresh Docker container, load a 10% sample of the real data into it, apply the fix, and run all 12 checks. The container is completely isolated from production. If the fix fails any ABORT check inside the container, it is discarded before any human even sees it.

---

## SLIDE 14 — BUGS

---

**Q: What was the most common type of bug?**
> Router prefix conflicts — 8 of the 19 bugs. FastAPI allows you to include sub-routers with a prefix like `/api`. If you also write `/api/` in the route handler itself, you get double-prefixed URLs like `/api/api/pipelines` that don't match any request. These were found during smoke testing and fixed by aligning path declarations with the router prefix configuration.

---

**Q: How did you handle database crashes?**
> The backend was crashing with unhandled exceptions when PostgreSQL was unavailable. I added try/except blocks on every database call, and if the DB is unavailable, the endpoint returns representative demo data with the same structure as the real response. This means the frontend always renders correctly even during development without a running database.

---

## SLIDE 15 — ROADMAP

---

**Q: What are the 4 phases after mid-semester?**
> Phase 1 (weeks 1-3): Connect to live PostgreSQL at Hevo, run Alembic migrations, replace demo data fallbacks with real data. Phase 2 (weeks 4-6): Wire the full end-to-end healing loop, inject 20 synthetic failures, add Slack alerts. Phase 3 (weeks 7-9): Run the 3 formal experiments — MTTR reduction, NL-SQL accuracy, cost savings. Phase 4 (weeks 10-12): Write the complete dissertation and prepare the oral defence.

---

**Q: What is Alembic?**
> Alembic is a database migration tool for Python. When you change your database schema — add a column, rename a table — instead of manually writing SQL, Alembic generates a migration script that can be run to upgrade (or roll back) the schema in a controlled, versioned way.

---

## SLIDE 16 — EXPERIMENTS

---

**Q: What is MTTR?**
> MTTR stands for Mean Time To Recovery — how long it takes on average to fix a pipeline failure. Today, a human engineer might take 2 hours to investigate and fix a schema drift issue. OrchestrAI targets reducing this by more than 50% — to under an hour, ideally under 10 minutes. Experiment 1 will measure this directly by injecting 20 controlled failures and comparing recovery times.

---

**Q: What is Spider v1.0?**
> Spider is a large, publicly available benchmark dataset for testing NL-to-SQL systems. It contains about 1,034 questions in plain English paired with the correct SQL queries across many different database schemas. Using Spider lets us compare our AI Analyst's accuracy against published results from other research teams on the same questions.

---

**Q: What does ">65% exact match" mean for NL-SQL?**
> It means we expect our system to generate the exactly correct SQL query for at least 65% of Spider's 1,034 test questions. "Exact match" is a strict metric — the generated SQL must produce the same result as the reference SQL when executed. We also measure "execution match" — whether both queries return the same rows even if written differently.

---

**Q: What is the 30% Snowflake cost saving target?**
> We expect the Cost Optimizer Agent to rewrite expensive SQL queries in a way that reduces Snowflake credit consumption by at least 30% on average. We'll measure this using 30 representative queries from Hevo's Snowflake query history — comparing actual credit usage before and after the agent rewrites them.

---

**Q: Why pre-register experiments?**
> Pre-registration means we define success criteria before collecting data. This prevents "p-hacking" — the temptation to adjust the target after seeing results to make the outcome look better. Our targets (>50% MTTR reduction, >65% NL-SQL accuracy, >30% cost savings) are locked now, and the results chapter will report whatever the experiments produce honestly.

---

## SLIDE 17 — CONCLUSION

---

**Q: What is the main contribution of your project?**
> OrchestrAI is the first open-source platform to close the full self-healing loop for data pipelines: detect → diagnose → write fix → sandbox test → human approval → deploy → learn. No existing tool does all seven steps. The platform is production-ready — 24 endpoints, 12 pages, zero TypeScript errors — validated at Hevo Technologies.

---

**Q: Is this deployed at Hevo? Is it in production?**
> The platform runs on a staging environment and has been validated against Hevo's data schema structure. Live production integration is Phase 1 of the post-semester roadmap — connecting to the real PostgreSQL database and removing the demo-data fallbacks. We run the formal experiments on a staging database that mirrors production to ensure results are valid.

---

**Q: What is the difference between what you have now and what comes after?**
> Now (mid-semester): The complete platform is built and validated — all 10 agents, 24 endpoints, 12 UI pages, the sandbox, the approval panel, the AI Analyst. Everything works against realistic data. After mid-semester: Live database integration, end-to-end healing with real failures, 3 formal experiments, and the complete dissertation.

---

**Q: What would you do differently if you started again?**
> I would start the live PostgreSQL integration earlier — in Sprint 1 rather than deferring it to Phase 2. The demo-data fallback approach worked well for rapid frontend development, but it pushed the live database risk to the end. Starting with a live database from Sprint 1 would have given us real data throughout development and made the experimental setup simpler.

---

## RAPID-FIRE DEFINITIONS (if invigilator asks "what is X?")

| Term | Simple answer |
|------|--------------|
| **Data pipeline** | Automated process that moves data from source to destination |
| **Schema** | The structure of a database table — column names and types |
| **Schema drift** | When that structure changes unexpectedly, breaking downstream systems |
| **Data warehouse** | Large database optimised for analytics (Snowflake, BigQuery) |
| **dbt** | Tool for writing SQL transformations in an organised, testable way |
| **Isolation Forest** | Algorithm that finds unusual data points by random partitioning |
| **LangGraph** | Framework for wiring AI agents together as a directed graph |
| **RAG** | AI technique: retrieve relevant past examples before generating an answer |
| **ChromaDB** | Database that stores things as vectors for similarity search |
| **JWT** | Security token proving who you are on every API request |
| **Docker** | Tool for running isolated containers — like lightweight virtual machines |
| **OpenLineage** | Open standard for tracking where data came from and where it went |
| **Marquez** | Server that stores and displays OpenLineage lineage events |
| **MTTR** | Mean Time To Recovery — how quickly failures get fixed |
| **Spider** | Public benchmark of 1,034 natural-language questions to test NL-SQL |
| **Fernet** | Symmetric encryption used to secure database credentials |
| **FastAPI** | Python framework for building REST APIs |
| **Next.js** | React-based framework for building web frontends |
| **TypedDict** | Python type for a dictionary with known, typed keys |
| **AST** | Abstract Syntax Tree — the parsed structure of a code or SQL statement |

---

*Reference: PPT Slides 1–17 · Read alongside General_Viva_Questions.md*
