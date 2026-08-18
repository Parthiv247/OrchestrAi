# Build the UI for "OrchestrAI" — an Autonomous Multi-Agent AI Data Platform

You are building a **production-grade web application UI** for a product called **OrchestrAI**. Read this entire brief before starting. I already have a working backend (FastAPI) and a first attempt at a frontend that I'm not happy with — I want you to **redesign the whole UI from scratch** into something that looks like a polished, modern SaaS product (think the visual quality of Linear, Vercel, Retool, Datadog, and Snowflake's Snowsight). You have creative freedom on the visual craft, but the **product, screens, data, and workflows described below must all be present**.

---

## 1. What OrchestrAI is (the product)

OrchestrAI is an **autonomous, multi-agent AI platform for self-healing data pipelines**. It sits on top of a company's data stack and does three things:

1. **Moves data** — connects data sources (PostgreSQL, REST APIs, Google Sheets, CSV/files, S3) to a data warehouse (Snowflake, BigQuery, Redshift, Postgres) through pipelines the user configures.
2. **Self-heals pipelines** — a team of AI agents continuously monitors pipelines, detects anomalies (zero rows loaded, row-count drops, null spikes, delays, repeated failures, ML-detected outliers), diagnoses the root cause, writes a code fix, tests the fix in a sandbox, and — after a human approves it — deploys it automatically. It learns from every incident.
3. **Turns data into insight** — a natural-language "AI Analyst" lets anyone ask questions in plain English and get back SQL + a results table + an auto-generated chart. A cost optimizer rewrites expensive warehouse queries to save money. A dbt assistant auto-generates transformation models.

**One-line pitch:** *"Self-Healing Data Pipelines · Adaptive Warehouse Optimization · Insight-Driven Visual Analytics — powered by a team of autonomous AI agents."*

**Who uses it:** data engineers, analytics engineers, and data analysts at companies. Roles are **Admin**, **Analyst/Editor**, and **Viewer** (RBAC). This is a serious internal B2B data tool, not a consumer app — density, clarity, and trustworthiness matter more than playful decoration.

**The AI agents (mention these in the product, e.g. in an incident timeline):**
- **MonitoringAgent** — watches pipeline metrics + runs an IsolationForest ML anomaly detector.
- **DiagnosisAgent** — finds the root cause using a dependency graph + an LLM.
- **FixWriterAgent** — generates the code fix.
- **SandboxAgent** — runs the fix in an isolated Docker sandbox to prove it works.
- **DeploymentAgent** — deploys the approved fix.
- **LearningAgent** — stores every incident + resolution in a vector memory so the system gets smarter over time.
- Plus **QueryAgent** (NL→SQL), **ValidationAgent** (SQL safety), and **CostOptimizerAgent** (query rewrite).

The LLM is **Groq (Llama 3.1 70B)** and the orchestration is **LangGraph** — the footer should read *"Powered by Groq + LangGraph."*

---

## 2. Tech stack you must build in

Please keep this exact stack so it drops into my codebase:

- **Next.js 14 (App Router)** + **React 18** + **TypeScript**
- **Tailwind CSS** + **shadcn/ui** components (Radix under the hood)
- **@tanstack/react-query** for data fetching/caching
- **axios** for the API client (base URL from `NEXT_PUBLIC_API_URL`, default `http://localhost:8000`)
- **recharts** for charts
- **framer-motion** for tasteful motion/transitions
- **lucide-react** for icons
- **date-fns** for time formatting
- A **WebSocket** hook for a real-time "Live" feed (pipeline status + incident updates)

Every screen fetches from a REST API (contract in §7). Build the data layer against these endpoints, but **ship realistic mock/fixture data** so every screen looks fully populated in a demo even without the backend running. Handle three states everywhere: **loading (skeletons)**, **empty**, and **error**.

---

## 3. Design direction (this is the part I care most about)

My current UI is a dark, glassmorphism dashboard (deep navy background, blue→purple gradients, frosted-glass cards). It's *fine* but it feels generic and a bit flat. **I want you to elevate it into something that feels genuinely premium and considered.** Guidance:

- **Overall vibe:** modern data-platform SaaS — confident, clean, information-dense but never cluttered. Trustworthy and "enterprise", with moments of delight (smooth transitions, live pulses, satisfying state changes). Think Linear's precision + Vercel's restraint + Datadog's data density.
- **Theme:** dark mode as the primary theme (this is a monitoring/ops tool — dark is expected). **Also ship a clean light mode** and a theme toggle. Don't rely on pure-black; use layered near-black/deep-slate surfaces with clear elevation.
- **Color:** keep a **blue → violet** brand accent, but make it purposeful, not everywhere. Use a disciplined semantic palette: green = healthy/success, amber = warning, red = failure/critical, blue = info/running, violet = AI/agent actions. Confidence scores, anomaly types, and pipeline health all need instantly-readable color coding.
- **Typography:** a crisp modern sans (Inter / Geist). Strong type hierarchy — big confident page headers, clear section labels, tabular numbers for metrics.
- **Surfaces:** you may use subtle glass/blur, but lean on **clear elevation, soft borders, and generous spacing** more than heavy frosted glass. Rounded corners (~8–12px). Subtle shadows/glows only to signal state (e.g. a soft green glow on healthy, red on critical).
- **Motion:** framer-motion for page/section entrance, list stagger, number count-ups on KPIs, and live status pulses. Keep it fast and subtle — nothing that slows the user down.
- **Data-viz:** charts should be beautiful and legible — thin gridlines, good empty states, consistent color mapping, nice tooltips.
- **Micro-states:** great skeletons, empty states with a helpful call-to-action, inline errors, toast notifications, copy-to-clipboard confirmations, and optimistic UI on actions.

Design a small, reusable **design system** first (tokens, buttons, cards, badges, tabs, dialogs, tables, inputs, metric cards, status badges, code blocks) and build every screen from it so the whole app feels consistent.

---

## 4. Global layout (shell)

- **Left sidebar (fixed, ~240px):** OrchestrAI logo ("O" mark in a blue→violet gradient tile) + "AI Data Platform" subtitle at top. Vertical nav with icon + label, an active-state indicator (accent bar + tint), and subtle entrance stagger. Footer line: ⚡ *"Powered by Groq + LangGraph."* Make it collapsible to an icon rail.
- **Top bar:** page title/breadcrumb, a **global search** (⌘K command palette — search pipelines, tables, incidents, nav), a **real-time "Live / Connecting / Offline" indicator** (green pulsing dot when the WebSocket is connected), notifications bell, theme toggle, and a user avatar menu (profile, role badge, sign out).
- **Content area:** comfortable padding, max-width where it helps readability, responsive down to tablet.

**Sidebar nav items (in this order), each is a full screen described in §5:**
1. Overview (dashboard)
2. Connectors
3. Pipelines
4. Approval Panel
5. Cost Optimizer
6. dbt Assistant
7. AI Analyst
8. Lineage
9. Observability
10. Data Quality
11. Reports
12. Settings

Plus a first-run **Onboarding** flow (§6).

---

## 5. Screens (build every one)

### 5.1 Overview (Dashboard) — route `/`
The command center. Contents:
- A **"Live" status pill** (WebSocket connected/connecting/offline).
- **4 KPI metric cards** (with count-up animation + tiny sparkline/trend): **Total Records Loaded** (e.g. "2.4M", subtitle "raw + staging tables"), **Active Incidents** (count; green when 0 = "All pipelines healthy", amber when >0 = "need attention"), **Cost Saved** (e.g. "$142.80", subtitle "from query rewrites"), **Agent Confidence** (e.g. "87%", subtitle "avg heal confidence").
- **Pipeline Health panel (wide):** list of pipelines, each row = source-type icon + friendly name (e.g. "PostgreSQL → Snowflake", "REST API (Weather) → Snowflake", "CSV Files → Snowflake", "Google Sheets → Snowflake") + a **status badge** (healthy/warning/failed) + a **"Trigger" button**. Header note: "Refreshes every 30s".
- **Recent Incidents panel (narrow):** last ~5 incidents, each = a color-coded **anomaly-type chip** (ZERO_LOAD=red, ROW_COUNT_DROP=amber, ML_ANOMALY=blue, NULL_SPIKE=violet, CONSECUTIVE_FAILURES=red, PIPELINE_DELAY=amber), the pipeline name, a confidence % , and relative time ("3 minutes ago").
- Real-time: when a pipeline fails or a new incident needs approval, show a toast and update the panels live.

### 5.2 Connectors — route `/connectors`
A **gallery of data connectors** (like Fivetran/Airbyte). Two groups: **Sources** (PostgreSQL, MySQL, REST API, Google Sheets, CSV/File upload, S3, Snowflake…) and **Destinations** (Snowflake, BigQuery, Redshift, PostgreSQL). Each connector is a card with a **brand logo** (fall back to an emoji/icon), name, category tag, and an "Add / Connect" action.
- A **"Saved connections"** section: list of configured connections with a status dot, a **"Test connection"** button (shows success/fail), and delete.
- **Add-connection flow:** a dialog/drawer with the right credential fields per connector type (host/port/db/user/password for Postgres; URL + headers for REST API; sheet URL for Google Sheets; a **drag-and-drop file upload** for CSV). Secrets shown masked.

### 5.3 Pipelines — route `/pipelines` (+ `/pipelines/new`, `/pipelines/[id]`)
- **List view:** cards/rows for each pipeline = source→destination, schedule label ("Manual", "Every 1 hour", "Every 6 hours", "Every 24 hours"… derived from cron), last-run status + records loaded, and actions: **Run now**, **View logs**, **Delete**.
- **Create pipeline wizard** (`/pipelines/new`) — a multi-step flow: **1) pick source → 2) pick destination → 3) field mapping (map source columns to destination columns) → 4) filters → 5) schedule (Manual / 30 min / hourly / 3h / 6h / 12h / daily / custom cron)**. Show a progress stepper and a review step.
- **Pipeline detail** (`/pipelines/[id]`): run history table (timestamps, status, rows, duration), a **logs viewer** (monospace, streaming feel), the schedule, and its incidents.

### 5.4 Approval Panel — route `/approvals`
The human-in-the-loop review queue for AI-proposed fixes. This is a hero screen — make it great.
- Tabs: **Pending**, **Approved**, **Rejected** (with counts), paginated.
- Each incident expands into a rich detail view showing the **agent timeline / reasoning**: the anomaly detected → DiagnosisAgent's **root-cause explanation** → FixWriterAgent's **proposed code fix (diff / code block with syntax highlighting)** → SandboxAgent's **test result** → a **confidence score**. 
- Big, clear **Approve** and **Reject** (with reason) buttons. On approve, show the DeploymentAgent deploying, then mark resolved (optimistic + toast). This screen should make a human feel confident approving an AI's code change.

### 5.5 Cost Optimizer — route `/optimizer`
- A **savings banner**: Total Saved ($), queries optimized, avg speedup %.
- A **SQL input** (code editor feel, monospace, with a sample query prefilled) + an **"Optimize" button**.
- Result view: **side-by-side "Original vs Optimized" SQL** (with syntax highlighting + copy button), plus metrics: **% faster**, **$ saved**, and a short explanation of *what* was rewritten (e.g. "replaced `SELECT *` with needed columns, added partition filter"). A small before/after cost bar chart.

### 5.6 dbt Assistant — route `/dbt`
- Left: a **model tree** grouped into **Staging** and **Marts** (collapsible), click a model to load it.
- A **"Generate models" action** that runs a 4-step animated progress: *"Introspecting schema… → Proposing star schema… → Writing SQL models… → Running dbt…"*.
- Right: a **SQL workbench** — editor where you can write SQL, click **Optimize** (reuses optimizer) or **Run**, and see results. Show recent **dbt runs** (status, timing).

### 5.7 AI Analyst — route `/analyst`
A **chat interface** for natural-language data questions (the flagship "wow" screen).
- Chat thread (user bubbles + assistant responses), a big input with **Send**, and **suggested questions** as chips (e.g. "How many records loaded today?", "Top 5 e-commerce categories by revenue", "Average taxi fare by vendor", "Show pipeline failure rate").
- Each assistant answer shows **three tabs: Chart / Table / SQL**. The **Chart** auto-renders the best recharts viz (bar/line/pie/scatter) from the returned rows; **Table** shows the raw result grid; **SQL** shows the generated query in a code block with copy. 
- Extras: **thumbs up/down feedback**, **download CSV**, **screenshot/export chart**, a **query history** drawer, and a **schema browser** (list of tables/columns you can click to reference). Show the executing/thinking state nicely.

### 5.8 Lineage — route `/lineage`
An **interactive data-lineage graph**: nodes flow left→right across layers **Source → Raw → Staging → Mart**, color-coded per layer (source=blue, raw=slate, staging=violet, mart=green), connected by edges. Clicking a node opens a side panel with the table's **columns (name, type, description)** and downstream/upstream dependencies. Make it feel like a real DAG (clean auto-layout, hover highlights the path).

### 5.9 Observability — route `/observability`
The metrics/monitoring screen. Time-series charts: **records loaded per pipeline over time** (stacked/multi-line, one color per pipeline), **run success/failure rate**, **latency/duration trends**, and an **anomaly/alert feed** with severity levels. Filters by pipeline and time range. This is the "Datadog for your pipelines" view.

### 5.10 Data Quality — route `/quality`
- A **summary header**: overall data-health score, # of tables monitored, # of active rules, failing checks.
- **Per-table health** list (row counts, null %, freshness, pass/fail).
- **Quality rules** management: create/edit/delete rules (e.g. "column X not null", "freshness < 24h"), toggle on/off, **Run** a rule on demand and see results.
- **Schema/data drift** view and a **PII scan** action (scan a table, flag columns that look like PII — email, phone, etc.).

### 5.11 Reports — route `/reports`
Scheduled email reports. List of configured reports (name, schedule, recipients, last sent), a **create-report** dialog (pick content + schedule + recipients), and a **"Send now"** action. Clean, form-driven.

### 5.12 Settings — route `/settings`
Tabbed settings: **Profile**, **Team** (invite users, assign roles Admin/Editor/Viewer with role badges), **API Keys** (create/copy/revoke keys), **Notifications** (Slack / email / webhook channels + alert rules + test button), **Connections** (managed data connections), **Audit Log** (activity history). Standard but polished settings UX with save confirmations.

---

## 6. Onboarding (first-run) — route `/onboarding`
A friendly **5-step guided setup** shown to new users (redirect here if `onboarding_complete` isn't set in localStorage):
1. **Welcome to OrchestrAI** — "Your autonomous AI platform for self-healing data pipelines."
2. **Connect a Data Source** → CTA to Connectors gallery.
3. **Add a Destination** (Snowflake / BigQuery / Redshift / Postgres) → CTA to Connectors.
4. **Build Your First Pipeline** (source → destination in 5 steps) → CTA to `/pipelines/new`.
5. **You're all set!** — "OrchestrAI will now monitor your pipeline, detect anomalies, and self-heal automatically." → Finish → dashboard.
Progress indicator, skippable, celebratory finish. Also include simple **Login / Register** screens (email + password, "register creates a new tenant") since the app is multi-tenant with JWT auth + RBAC.

---

## 7. API contract (build the data layer to match)

Base URL from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). In non-prod, send header `X-Dev-Mode: true` (auth bypass for local dev). Endpoints already implemented on the backend — wire React Query to these and mirror their shapes in your mock data:

- **Pipelines:** `GET /api/pipelines`, `POST /api/pipelines/{id}/trigger`, `DELETE /api/pipelines/{id}`, `GET /api/pipelines/{id}/runs`, `GET /api/connections`
- **Self-healing / incidents:** `GET /api/incidents` (params `limit,offset,status`), `GET /api/incidents/{id}`, `POST /api/healing/trigger/{name}`, `GET /api/healing/status`, `POST /api/incidents/{id}/approve?token=…`, `POST /api/incidents/{id}/reject?token=…` (body `{reason}`)
- **AI Analyst:** `POST /api/analyst/query` (`{question, session_id}` → returns `{sql, columns, rows, chart_config, id}`), `POST /api/analyst/execute` (`{sql, user_role}`), `GET /api/analyst/tables`, `GET /api/analyst/tables/{table}/schema?schema=marts`, `POST /api/analyst/query/{id}/feedback` (`{feedback}`)
- **Insights:** `GET /api/insights`, `POST /api/insights/refresh`, `GET /api/insights/{id}/data`
- **Optimizer:** `POST /api/optimize/query` (`{sql}` → `{optimized_sql, savings_percent, dollar_savings, explanation}`), `GET /api/optimize/savings`
- **dbt:** `POST /api/dbt/generate`, `GET /api/dbt/models`, `GET /api/dbt/runs`
- **Stats:** `GET /api/stats/overview` (→ `{total_records_loaded, …}`), `GET /api/metrics/history`, `GET /api/learning/stats`
- **Connectors:** `GET /api/connectors/catalog`, `GET /api/connectors/saved`, `POST /api/connectors/saved`, `DELETE /api/connectors/saved/{id}`, `POST /api/connectors/saved/{id}/test`, `POST /api/connectors/upload` (multipart)
- **Quality:** `GET /api/quality/summary`, `GET /api/quality/tables`, `GET /api/quality/rules`, `POST /api/quality/rules`, `DELETE /api/quality/rules/{id}`, `POST /api/quality/rules/{id}/run`, `POST /api/quality/rules/{id}/toggle`, `GET /api/quality/drift`, `POST /api/quality/pii-scan` (`{table}`)
- **Reports:** `GET /api/reports`, `POST /api/reports`, `DELETE /api/reports/{id}`, `POST /api/reports/{id}/send`
- **Notifications/Settings:** `GET/POST /api/settings/notifications`, `GET /api/notifications/alert-rules`, `GET /api/notifications/history`, `POST /api/notifications/alert-rules/{id}/toggle`, `DELETE /api/notifications/alert-rules/{id}`, `POST /api/notifications/dispatch`, `POST /api/notifications/test` (`{channel}`)
- **WebSocket:** a live channel that pushes `{type: 'pipeline_status', data:{pipeline_id,status}}` and `{type: 'incident_update', data:{incident_id,status}}` — drive the "Live" indicator, toasts, and auto-refresh from it.

**Key data shapes to reflect in mock data:**
- *Pipeline:* `{ id, dag_id, name, source_type, schedule/cron, last_run: { status: 'success'|'failed'|null, records_loaded } }`
- *Incident:* `{ id, pipeline_name, anomaly_type: 'ZERO_LOAD'|'ROW_COUNT_DROP'|'ML_ANOMALY'|'NULL_SPIKE'|'CONSECUTIVE_FAILURES'|'PIPELINE_DELAY', confidence_score (0–1), approval_status: 'pending'|'approved'|'rejected', root_cause, proposed_fix (code), sandbox_result, created_at }`
- *Analyst result:* `{ id, sql, columns: string[], rows: any[][], chart_config: { type:'bar'|'line'|'pie'|'scatter', x_column, y_column } }`

---

## 8. Deliverables & acceptance criteria

- All **12 nav screens + onboarding + login/register** built and navigable, in **Next.js 14 App Router + TS + Tailwind + shadcn**, using the stack in §2.
- A cohesive **design system** (tokens, dark + light themes, reusable components) applied consistently across every screen.
- **Loading / empty / error** states everywhere; **toasts**, **skeletons**, **copy-to-clipboard**, and **optimistic actions**.
- **Realistic mock data** so every screen looks alive in a demo; real API calls wired via React Query to the §7 endpoints (env-configurable base URL).
- **Real-time "Live" indicator** + toasts driven by a WebSocket hook.
- Responsive (desktop-first, graceful on tablet), accessible (keyboard nav, focus states, good contrast), and fast.
- Polished **AI Analyst chat**, **Approval Panel agent-timeline**, and **Overview dashboard** — these three are the demo showpieces; make them exceptional.

Make it feel like a product I'd be proud to demo to investors and to my MTech final-semester review committee. Prioritize clarity, trust, and craft. Surprise me on the visual design — just keep every feature and workflow above intact.

---

## 9. Visual references (mimic the craft, not the exact look)

Use these as inspiration for quality and specific patterns — I want OrchestrAI to feel like it belongs in this class of product:

- **Linear** (linear.app) — typography, spacing discipline, keyboard-first feel, the ⌘K command palette, buttery transitions. *Steal:* the overall restraint and polish.
- **Vercel dashboard** (vercel.com) — clean dark surfaces, elevation, deployment/log views. *Steal:* the pipeline run + logs screens.
- **Datadog / Grafana** — dense time-series monitoring, severity color-coding, alert feeds. *Steal:* the Observability screen.
- **Snowflake Snowsight** & **Retool** — SQL workbench + results grid + chart tabs. *Steal:* the AI Analyst and dbt workbench layouts.
- **Fivetran / Airbyte** — connector gallery cards with brand logos, connection setup drawers. *Steal:* the Connectors screen.
- **dbt Cloud / Atlan / OpenLineage** — the lineage DAG (source→raw→staging→mart), model tree, column-level metadata panels. *Steal:* the Lineage and dbt Assistant screens.
- **Cursor / GitHub PR review** — clean code-diff blocks with syntax highlighting + approve/reject. *Steal:* the Approval Panel fix-review view.

**Motion/quality bar:** KPI number count-ups, list stagger on load, a soft live pulse on the "Live" dot, smooth tab/route transitions, and satisfying approve→deploy→resolved state changes. Nothing gratuitous — every animation should communicate state.

**Do NOT copy** any brand's exact colors or logo. OrchestrAI keeps its own blue→violet identity. These are references for *craft, density, and interaction patterns* only.

---

## 10. Condensed version (paste this if you have a character/input limit)

> Build a production-grade web app UI for **OrchestrAI**, an autonomous multi-agent AI platform for **self-healing data pipelines**. It (1) moves data from sources (PostgreSQL, REST API, Google Sheets, CSV/S3) to warehouses (Snowflake/BigQuery/Redshift/Postgres) via user-configured pipelines; (2) uses a team of AI agents to monitor pipelines, detect anomalies (zero-load, row-count drop, null spike, delay, failures, ML outliers), diagnose root cause, write a code fix, sandbox-test it, and — after human approval — auto-deploy and learn from it; (3) turns data into insight via a natural-language "AI Analyst" (English → SQL + table + auto-chart), a warehouse **cost optimizer** (rewrites queries to save money), and a **dbt assistant** (auto-generates models). LLM = Groq Llama 3.1 70B, orchestration = LangGraph. B2B data tool with RBAC (Admin/Analyst/Viewer), multi-tenant, JWT auth.
>
> **Stack:** Next.js 14 App Router + React 18 + TypeScript + Tailwind + shadcn/ui + @tanstack/react-query + axios + recharts + framer-motion + lucide-react. Fetch from a FastAPI backend at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`), but ship realistic mock data so every screen looks alive. Handle loading (skeletons) / empty / error states everywhere, plus toasts and a WebSocket "Live" indicator.
>
> **Design:** premium modern data-platform SaaS — the craft of Linear + Vercel + Datadog. Dark-mode-primary with a clean light mode + toggle. Blue→violet brand accent used purposefully; strict semantic colors (green=healthy, amber=warning, red=critical, blue=info, violet=AI). Crisp Inter/Geist type, layered elevation over heavy glass, tasteful framer-motion. Build a reusable design system first, then every screen from it.
>
> **Shell:** fixed left sidebar (logo + 12 nav items, collapsible) + top bar (⌘K global search, Live indicator, notifications, theme toggle, user/role menu).
>
> **Screens (build all):** 1) **Overview** dashboard — 4 KPI cards (Total Records Loaded, Active Incidents, Cost Saved, Agent Confidence), Pipeline Health list with status badges + Trigger, Recent Incidents with color-coded anomaly chips + confidence %, live updates. 2) **Connectors** — Fivetran-style gallery of source/destination connectors with brand logos, saved connections with test-connection, add-connection drawer with per-type credential fields + CSV drag-drop. 3) **Pipelines** — list with schedule labels + run/logs/delete, a 5-step create wizard (source→destination→field mapping→filters→schedule/cron), and a detail page with run history + streaming logs. 4) **Approval Panel** — human-in-the-loop queue (Pending/Approved/Rejected tabs) where each incident expands into an agent timeline: anomaly → root-cause → proposed code fix (syntax-highlighted diff) → sandbox test result → confidence score, with big Approve/Reject buttons. 5) **Cost Optimizer** — savings banner + SQL editor → side-by-side original vs optimized SQL with % faster / $ saved / explanation. 6) **dbt Assistant** — staging/marts model tree + a 4-step "generate models" animation + SQL workbench (optimize/run) + recent runs. 7) **AI Analyst** — chat UI with suggested-question chips; each answer has Chart/Table/SQL tabs (auto-rendered recharts viz), thumbs feedback, CSV export, query history, schema browser. 8) **Lineage** — interactive DAG source→raw→staging→mart, color-coded layers, click a node for columns/metadata. 9) **Observability** — time-series charts (records loaded per pipeline, success/failure rate, latency) + severity-coded alert feed + filters. 10) **Data Quality** — health score, per-table checks, quality-rule CRUD + run/toggle, drift view, PII scan. 11) **Reports** — scheduled email reports (create/schedule/recipients/send-now). 12) **Settings** — tabs: Profile, Team (invite + roles), API Keys, Notifications (Slack/email/webhook + test), Connections, Audit Log. Plus a 5-step **Onboarding** flow (welcome → connect source → add destination → build first pipeline → done) and **login/register**.
>
> Deliver a cohesive, responsive, accessible app where the **Overview dashboard, AI Analyst chat, and Approval Panel** are the standout demo screens. Footer: "Powered by Groq + LangGraph." Surprise me on the visuals — keep every feature intact.
