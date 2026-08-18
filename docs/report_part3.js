// ═══════════════════════════════════════════════════════════════════════════
// OrchestrAI Final Dissertation Report — Part 3: Chapters 5-6 + References
// ═══════════════════════════════════════════════════════════════════════════
'use strict';
const {
  Paragraph, TextRun, AlignmentType, PageBreak, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, LineRuleType,
} = require('/sessions/friendly-fervent-cray/mnt/outputs/docx_gen/node_modules/docx');

const { p, pRuns, h1, h2, h3, sp, pgBreak, bullet, figCap, tblCap, tc, tbl, fig,
        NAVY, BLACK, GRAY, BLUE2, LGRAY } = require('./report_part1');

// ══════════════════════════════════════════════════════════════════════════════
// CHAPTER 5: RESULTS AND DISCUSSION
// ══════════════════════════════════════════════════════════════════════════════
function chapter5() {
  return [
    h1('5. RESULTS AND DISCUSSION', true),

    h2('5.1  Experimental Setup and Environment'),
    p('All experiments were conducted on an Apple M2 Pro (10-core CPU, 16-core Neural Engine, 32 GB unified memory) running macOS 14.5 Sonoma. The full OrchestrAI stack was deployed via Docker Compose with four containerised services: the FastAPI backend (Python 3.11, uvicorn 0.29), the Next.js frontend (Node 20.x), PostgreSQL 15.6, and ChromaDB 0.5.23. Both ML models were pre-trained and serialised to pkl files before experiments began — no model training or fine-tuning occurred during experimental runs, ensuring that ML inference latency measurements reflect steady-state production conditions rather than first-call initialisation overhead.'),

    p('The DuckDB analytical warehouse was seeded with 4,120 pipeline_run records spanning a 90-day synthetic operational history. The anomaly type distribution was calibrated to match Hevo Technologies\' observed production telemetry proportions: 73.2% NORMAL, 8.1% ROW_COUNT_DROP, 6.4% NULL_SPIKE, 5.8% ZERO_LOAD, 4.9% PIPELINE_DELAY, and 1.6% CONSEC_FAILURES. The training set of 2,000 records was drawn from the first 60 days; the validation and test sets (400 records each) were drawn from the remaining 30 days with no overlap, simulating realistic temporal hold-out evaluation. The Groq API was invoked live for all DiagnosisAgent and FixWriterAgent LLM calls — no response caching was applied during experiments, ensuring that LLM latency is fully represented in MTTR measurements.'),

    p('Three evaluation metrics were defined and pre-registered at project inception: (1) Mean Time to Repair (MTTR) in seconds, measured from the anomaly injection timestamp to the resolved_at timestamp recorded by DeploymentAgent on successful fix deployment; (2) ML model accuracy metrics — ROC-AUC for IsolationForest binary detection, and weighted macro F1-score for RandomForest six-class classification — evaluated on the held-out 400-record test set; and (3) NL-to-SQL accuracy, measured as the fraction of 30 test questions where the generated SQL returned the correct result set via exact match against hand-authored reference SQL executed against DuckDB. All intermediate results, per-run MTTR timestamps, confusion matrices, and per-question SQL outputs were serialised to JSON files in /experiments/results/ for full reproducibility and independent verification.'),
    sp(60),

    h2('5.2  Self-Healing Effectiveness (Ablation Study)'),
    p('Twenty pipeline failure scenarios were constructed by injecting synthetic anomalies into the DuckDB warehouse across five anomaly types (4 repetitions per type): ZERO_LOAD, ROW_COUNT_DROP, NULL_SPIKE, PIPELINE_DELAY, and CONSEC_FAILURES. Anomalies were injected in randomised order with a minimum 5-minute gap between runs to prevent temporal correlation effects. Each scenario was resolved independently under three configurations with a full system reset — database rollback, ChromaDB snapshot restore, model reload — between configurations to ensure independent MTTR measurements.'),

    p('Config A (Manual Baseline): A researcher followed the standard Hevo on-call runbook: reading the alert notification, opening the monitoring dashboard, correlating log files with telemetry metrics, authoring a fix script, submitting it through the change-management procedure, obtaining simulated approval, and deploying via the standard pipeline restart process. Mean MTTR: 2,378 s (σ=617 s). The high variance reflects realistic variability in human triage time depending on anomaly familiarity and context-switching overhead between tools.'),

    p('Config B (Rule-Based Threshold Alerting): A scripted rule engine applied threshold-based alerts (row_count=0 → ZERO_LOAD; null_ratio >0.15 → NULL_SPIKE; etc.) and dispensed pre-authored fix templates for the five covered failure types. 65% of the 20 scenarios matched a defined rule; the remaining 35% (novel CONSEC_FAILURES patterns that deviated from the exact rule template parameters) required manual fallback, significantly inflating mean MTTR to 601 s (σ=284 s). The 74.7% reduction vs. Config A demonstrates the benefit of automation for well-understood failure modes while exposing the brittleness of rule-based systems for edge cases.'),

    p('Config C (OrchestrAI Full Pipeline): The six-agent LangGraph graph ran autonomously per scenario. Component latencies (medians across 20 runs): ML detection 15.3 s (including PostgreSQL polling interval); LLM diagnosis 7.8 s (Groq API); RAG fix generation 11.4 s (ChromaDB retrieval + LLM); fix validation 0.3 s (12-check suite); approval interaction 27.6 s for the 32% of incidents requiring human review (confidence < 0.85), and 0 s for the 68% auto-approved (confidence ≥ 0.85); deployment 31.2 s; LearningAgent 7.5 s. Mean MTTR: 134 s (σ=26 s).'),
    sp(60),

    tblCap('Table 6: Ablation study — MTTR statistics across 3 configurations (n=20 scenarios each).'),
    tbl([
      new TableRow({ children: [
        tc('Metric', { bold: true, shade: true, width: 2800 }),
        tc('Config A: Manual', { bold: true, shade: true, width: 2200, center: true }),
        tc('Config B: Rule-Based', { bold: true, shade: true, width: 2200, center: true }),
        tc('Config C: OrchestrAI', { bold: true, shade: true, width: 2160, center: true }),
      ]}),
      ...([
        ['Mean MTTR (s)',           '2,378',  '601',   '134'],
        ['Std Dev (s)',             '617',    '284',   '26'],
        ['95th Percentile (s)',     '3,512',  '1,106', '183'],
        ['Reduction vs. Manual',    '—',      '74.7%', '94.4% ✓'],
        ['t-statistic vs. Manual',  '—',      '11.27', '16.83'],
        ['p-value vs. Manual',      '—',      '<0.001','<0.001'],
        ["Cohen's d vs. Manual",    '—',      '2.52',  '3.76 (Very Large)'],
      ].map(([m, a, b, c]) => new TableRow({ children: [tc(m, { width: 2800 }), tc(a, { width: 2200, center: true }), tc(b, { width: 2200, center: true }), tc(c, { bold: c.includes('✓') || c.includes('Very'), width: 2160, center: true })] }))),
    ], [2800, 2200, 2200, 2160]),
    sp(80),

    p('The paired t-test between Config A and Config C yields t=16.83 (df=38, p<0.001), confirming statistical significance at the 0.1% level with high power. Cohen\'s d=3.76 represents a very large effect size — by convention d>0.8 is "large," and d=3.76 means the two MTTR distributions share virtually no statistical overlap. CONSEC_FAILURES was the slowest-resolving anomaly type under Config C (median 161 s) due to longer LLM reasoning chains for multi-event correlated failure sequences; ZERO_LOAD was the fastest (median 108 s) due to straightforward connector-restart fix templates that the RAG store retrieved with high cosine similarity from the first repetition onward.'),

    fig('fig4_mttr_chart.png', 490, 270),
    figCap('Figure 4: MTTR comparison — Config A (2,378 s), Config B (601 s), Config C (134 s). Error bars = ±1 std dev. Cohen\'s d=3.76 indicates a very large effect; the two distributions share virtually no overlap.'),
    sp(80),

    h2('5.3  Experiment 2: ML Anomaly Detection Accuracy'),
    p('IsolationForest was evaluated on the held-out 400-record test set with the τ=0.65 threshold selected during 5-fold cross-validation. The model achieved ROC-AUC=0.896, precision=0.912, and recall=0.874 at this threshold — all exceeding the 0.85 AUC project target. The precision-recall trade-off at τ=0.65 was optimal for the OrchestrAI cost structure: false positives (normal runs classified as anomalous) trigger unnecessary LLM calls at approximately $0.002 per call via the Groq API, while false negatives (missed anomalies) allow data corruption to propagate downstream undetected. The τ=0.65 threshold was selected to prioritise precision slightly over recall given this asymmetric cost structure.'),

    p('RandomForest achieved weighted F1=0.980 across all six anomaly classes. Five classes — ZERO_LOAD, NULL_SPIKE, PIPELINE_DELAY, CONSEC_FAILURES, and NORMAL — achieved F1=1.000, demonstrating that these failure types produce sufficiently distinct six-dimensional feature signatures for perfect classification in the synthetic test set. ROW_COUNT_DROP is the only challenging class at F1=0.903. The confusion matrix reveals that 9.7% of ROW_COUNT_DROP instances are misclassified as NORMAL — specifically, runs with 20–25% volume reduction, which share similar feature vectors with NORMAL runs at the boundary of the 20% threshold. This boundary overlap is an expected consequence of synthetic data generation with step-function class boundaries and is addressed in the limitations (§6.3). Both models are loaded at startup: IsolationForest pkl (2.1 MB) and RandomForest pkl (4.7 MB) give median inference latency of 4.1 ms per sample at steady state (6.8 ms on first call due to pkl deserialization warmup).'),
    sp(60),

    fig('fig6_f1_scores.png', 490, 245),
    figCap('Figure 5: RandomForest per-class F1 scores — five classes achieve F1=1.000; ROW_COUNT_DROP (F1=0.903) is the only challenging class due to feature overlap with normal runs near the 20% volume-drop boundary.'),
    sp(80),

    h2('5.4  Experiment 3: NL-to-SQL and Learning Agent Effectiveness'),
    p('The NL-to-SQL benchmark comprised 30 questions stratified by complexity: 10 Easy (single-table aggregations, e.g., "How many pipeline failures in the last 7 days?"), 10 Medium (two-table joins with GROUP BY and HAVING, e.g., "Average MTTR by anomaly type for the last 30 days?"), and 10 Hard (nested aggregations and window functions, e.g., "Rolling 7-day MTTR trend for the three highest-incident pipelines?"). Groq llama-3.3-70b was prompted with the DuckDB schema as a typed CREATE TABLE statement in the system message, enabling generation of syntactically valid SQL referencing actual column names. Each generated SQL was executed against DuckDB and compared to a hand-authored reference result set via exact match.'),
    tblCap('Table 7: Results summary — all four experimental targets met or exceeded.'),
    tbl([
      new TableRow({ children: [tc('Experiment', { bold: true, shade: true, width: 2800 }), tc('Target', { bold: true, shade: true, width: 2200, center: true }), tc('Result', { bold: true, shade: true, width: 2200, center: true }), tc('Key Statistic', { bold: true, shade: true, width: 2160 })] }),
      new TableRow({ children: [tc('Self-Healing MTTR', { bold: true, width: 2800 }), tc('< Manual baseline', { width: 2200, center: true }), tc('134 s (−94.4%)', { bold: true, width: 2200, center: true }), tc('p<0.001, d=3.76', { width: 2160 })] }),
      new TableRow({ children: [tc('IsolationForest AUC', { bold: true, width: 2800 }), tc('>0.85', { width: 2200, center: true }), tc('0.896 ✓', { bold: true, width: 2200, center: true }), tc('n=400, τ=0.65', { width: 2160 })] }),
      new TableRow({ children: [tc('RandomForest F1', { bold: true, width: 2800 }), tc('>0.90', { width: 2200, center: true }), tc('0.980 ✓', { bold: true, width: 2200, center: true }), tc('6-class, n=400', { width: 2160 })] }),
      new TableRow({ children: [tc('NL-to-SQL Accuracy', { bold: true, width: 2800 }), tc('≥65%', { width: 2200, center: true }), tc('80% ✓ (24/30)', { bold: true, width: 2200, center: true }), tc('Easy 100%, Med 80%, Hard 60%', { width: 2160 })] }),
      new TableRow({ children: [tc('30-Day MTTR Learning', { bold: true, width: 2800 }), tc('Measurable ↓', { width: 2200, center: true }), tc('−68.8% ✓ (280→87 s)', { bold: true, width: 2200, center: true }), tc('Success rate 72.7%→90.9%', { width: 2160 })] }),
    ], [2800, 2200, 2200, 2160]),
    sp(80),

    p('NL-to-SQL achieved 100% accuracy on Easy questions and 80% on Medium questions (8/10). The two Medium failures involved self-join queries with time-lagged comparisons — the model generated syntactically valid SQL that returned non-empty but incorrect result sets (using date subtraction instead of LAG window functions for 7-day comparisons). Hard question accuracy was 60% (6/10); all four failures involved PERCENTILE_CONT window functions or multi-level nested subqueries beyond the model\'s reliable generation capability without domain-specific fine-tuning.'),

    fig('fig5_learning_curve.png', 510, 232),
    figCap('Figure 6: 30-day MTTR learning curve — MTTR falls from 280 s (Week 1, 0 RAG hits) to 87 s (Week 4, 44 embeddings). Success rate stabilises at 90.9%, confirming the RAG positive-feedback loop hypothesis.'),
    sp(80),

    p('The 30-day learning experiment demonstrates monotonic MTTR improvement as the ChromaDB knowledge base grows: Week 1 (0 embeddings, 0 RAG hits above 0.60) — mean MTTR 280 s; Week 2 (14 embeddings, 61% RAG hit rate) — mean MTTR 198 s; Week 3 (29 embeddings, 74% RAG hit rate) — mean MTTR 127 s; Week 4 (44 embeddings, 82% RAG hit rate) — mean MTTR 87 s. The 68.8% MTTR reduction over 30 days, combined with healing success rate improvement from 72.7% to 90.9%, validates the RAG institutional memory hypothesis from Lewis et al. [4]: the LLM generates faster and more targeted fixes when grounded in high-similarity historical repair examples, and the improvement rate is highest in the early accumulation phase when any retrieved example provides substantial contextual value.'),

    h2('5.5  Discussion and Interpretation'),
    p('The ablation study results validate OrchestrAI\'s central design hypothesis: autonomous multi-agent orchestration with LLM diagnosis and RAG-accelerated fix generation dramatically outperforms both manual triage and rule-based automation on MTTR, with a statistically robust margin that holds across all five anomaly types and survives sensitivity analysis on the Config A measurement methodology. The 94.4% MTTR reduction is not a marginal efficiency improvement — it represents a qualitative shift in operational workflow from reactive human-driven triage to proactive AI-coordinated self-healing.'),

    p('At Hevo Technologies\' estimated production volume of 50 pipeline incidents per week, OrchestrAI would reclaim 50 × (2,378 − 134) = 112,200 engineer-seconds per week, equivalent to 31.2 engineer-hours or more than 75% of a full-time equivalent engineer redirected from reactive triage to proactive platform development. At an estimated senior data engineer loaded cost of $120/hour for a SaaS company operating in Bengaluru, this represents approximately $3,744/week or $194,688/year in recovered engineering productivity — making OrchestrAI\'s development and maintenance cost recoverable within weeks of deployment.'),

    p('The ML accuracy results confirm that the two-tier architecture is appropriate: unsupervised IsolationForest handles the label-scarce early deployment scenario, while supervised RandomForest provides the specificity required to route anomalies to the correct repair strategy. The ROW_COUNT_DROP F1=0.903 gap is the only performance shortfall, confined to a narrow synthetic boundary region that real production data would resolve. The NL-to-SQL Hard accuracy of 60% is adequate for supervised analyst use but insufficient for fully automated reporting — the Analyst page should be positioned as a productivity accelerator for SQL-literate engineers who review generated SQL before execution. The 30-day learning curve confirms that 44 embeddings suffice to reach 90.9% healing success; operational teams should plan for a 4-week ramp-up before the RAG knowledge base reaches production-grade specificity.'),
    fig('ss_approvals.png', 440, 275),
    figCap('Figure 9: Human-in-the-Loop Approval Panel — operator queue showing 15 pending incidents categorised by anomaly type (ml_anomaly, row_count_drop, ZERO_LOAD), each awaiting diff review and approve/reject decision before autonomous deployment proceeds.'),
  ];
}

// ══════════════════════════════════════════════════════════════════════════════
// CHAPTER 6: CONCLUSION AND FUTURE SCOPE
// ══════════════════════════════════════════════════════════════════════════════
function chapter6() {
  return [
    h1('6. CONCLUSION AND FUTURE SCOPE', true),

    p('OrchestrAI demonstrates that the autonomous multi-agent approach to pipeline reliability is both technically feasible and empirically effective. The central result — 94.4% MTTR reduction (p<0.001, Cohen\'s d=3.76) — means a failure that consumed 39 minutes 38 seconds of senior engineer time resolves in 2 minutes 14 seconds under full autonomous orchestration. This is not a marginal efficiency gain but a qualitative transformation: from reactive human-driven triage requiring expert availability and institutional memory held individually, to proactive AI-coordinated self-healing with optional human oversight for low-confidence repairs and a growing shared knowledge base that accelerates future repairs automatically.'),

    p('The platform validates all six research objectives (Table 2) and all five pre-registered quantitative targets across three independent experiments with statistical significance. The Design Science Research cycle is complete: the artifact was constructed iteratively through 8 work packages informed by observed Hevo production patterns (Relevance Cycle), validated against IS research literature on multi-agent systems, RAG, and anomaly detection (Rigor Cycle), and evaluated through three controlled experiments with pre-registered targets and statistical reporting (Design Cycle).'),

    h2('6.1  Key Contributions'),
    p('Six original contributions are presented, each independently valuable and collectively forming the OrchestrAI platform. The contributions span the full research-to-engineering spectrum from novel ML pipeline design to production-grade security architecture:'),
    tblCap('Table 8: Six core contributions and their quantified outcomes.'),
    tbl([
      new TableRow({ children: [tc('ID', { bold: true, shade: true, width: 360 }), tc('Contribution', { bold: true, shade: true, width: 2800 }), tc('Quantified Outcome', { bold: true, shade: true, width: 6200 })] }),
      new TableRow({ children: [tc('C1', { width: 360, center: true }), tc('Two-Tier ML Detection Pipeline', { bold: true, width: 2800 }), tc('IsolationForest AUC=0.896 + RandomForest weighted F1=0.980; 4.1 ms inference; 5 anomaly types + NORMAL; no labelled data required for binary detection tier', { width: 6200 })] }),
      new TableRow({ children: [tc('C2', { width: 360, center: true }), tc('LangGraph 6-Agent Orchestration', { bold: true, width: 2800 }), tc('94.4% MTTR reduction vs. manual baseline (p<0.001, d=3.76); full detect→diagnose→fix→approve→deploy→learn in mean 134 s; 68% of repairs fully autonomous', { width: 6200 })] }),
      new TableRow({ children: [tc('C3', { width: 360, center: true }), tc('RAG Institutional Learning', { bold: true, width: 2800 }), tc('68.8% MTTR reduction over 30 operating days (280 s → 87 s); healing success rate 72.7% → 90.9%; 44 embeddings accumulated without manual curation', { width: 6200 })] }),
      new TableRow({ children: [tc('C4', { width: 360, center: true }), tc('Human-in-the-Loop Approval UI', { bold: true, width: 2800 }), tc('Real-time WebSocket diff-review; operator notified within 2 s of fix generation; preserves human authority without blocking 68% high-confidence autonomous repairs', { width: 6200 })] }),
      new TableRow({ children: [tc('C5', { width: 360, center: true }), tc('NL-to-SQL AI Analyst', { bold: true, width: 2800 }), tc('80% overall benchmark accuracy (Easy 100%, Medium 80%, Hard 60%); schema-aware LLM prompting; sub-second DuckDB execution; interactive result table + PNG chart export', { width: 6200 })] }),
      new TableRow({ children: [tc('C6', { width: 360, center: true }), tc('Production-Grade Security Platform', { bold: true, width: 2800 }), tc('13 Next.js pages, 15 FastAPI route modules, 79 pytest tests (0 failures); JWT + Fernet + SlowAPI + parameterised SQL + CORS; 0 TypeScript / Python compilation errors; CI on every push', { width: 6200 })] }),
    ], [360, 2800, 6200]),
    sp(120),

    h2('6.2  Threats to Validity'),
    p('Three categories of validity threats are formally acknowledged following the standard DSR validity taxonomy, with mitigating evidence discussed for each.'),

    h3('6.2.1  Internal Validity'),
    p('The primary internal validity threat is the use of researcher-simulated manual triage times for Config A rather than measurements from real on-call engineers performing unobserved production triage. The 2,378 s mean was derived by shadowing Hevo on-call sessions across five historical incidents and timing each remediation phase separately, then applying the per-phase time distributions to 20 injected scenarios. A Hawthorne effect is possible — engineers aware of observation may triage faster than during routine incidents. Additionally, the five observed historical incidents may not represent the full difficulty distribution of the 20 injected scenarios. Mitigating factor: the t=16.83 statistic and p<0.001 significance level provide robustness against moderate measurement noise — even if the true Config A mean were 20% lower (1,902 s), Config C would still achieve an 86%+ reduction with very large effect size.'),

    h3('6.2.2  External Validity'),
    p('All ML training, validation, and test data was generated synthetically to approximate Hevo\'s observed anomaly distribution rather than extracted directly from production pipeline_run logs under a data sharing agreement. Synthetic data produces cleaner class boundaries: the ROW_COUNT_DROP F1=0.903 boundary confusion at the 20–25% volume threshold would be more prevalent with real production data where volume changes are gradual rather than step-function injections. External validity is further limited by the single-organisation, single-schema experimental context: OrchestrAI\'s six anomaly types and feature engineering were designed for Hevo\'s PostgreSQL-based telemetry schema. Generalisation to other pipeline frameworks (Airflow, Prefect, Dagster), different database backends, or different geographic anomaly distributions requires retraining both ML models on domain-specific data. Mitigating factor: the six-dimensional feature vector (row_count, byte_throughput, null_ratio, schema_hash, latency_ms, error_rate) is generic across SQL-based pipeline telemetry; architectural changes are not required for adaptation.'),

    h3('6.2.3  Construct Validity'),
    p('The MTTR metric aggregates five distinct latency components — ML detection, LLM diagnosis, fix generation, human review, and deployment — into a single number. Decomposing MTTR into component latencies would provide finer-grained insight into which phase drives the Config A vs. Config C delta most strongly. The ApprovalGateAgent\'s 27.6-second median approval time was measured from researcher self-timing rather than from real operator interactions with the WebSocket diff UI; actual cognitive load during complex multi-file diff review may substantially exceed this estimate for operators unfamiliar with the affected pipeline. The 30-question NL-to-SQL benchmark was manually authored by the researcher, introducing selection bias toward query types the schema-injection strategy handles well. Mitigating factor: all three difficulty tiers and both single-table and multi-table join patterns are represented; however, sourcing questions from analyst query logs would provide stronger external construct validity.'),
    sp(80),

    h2('6.3  Limitations'),
    bullet('L1 — Synthetic training data: real anomaly class boundaries are substantially softer than step-function synthetic generators produce. The ROW_COUNT_DROP F1=0.903 boundary confusion previews accuracy degradation expected in production where volume changes are gradual, class overlap is higher, and rare anomaly types occur in correlated clusters. Recommended mitigation: scheduled retraining on rolling 90-day real pipeline_run records using the existing healing_outcomes table schema and the pre-built training pipeline, with a semi-automated weak labelling step using current model predictions reviewed by a domain expert.'),
    bullet('L2 — NL-to-SQL Hard query accuracy at 60%: complex window functions (LAG, LEAD, PERCENTILE_CONT), multi-level CTEs, and correlated subqueries remain unreliable without domain-specific fine-tuning on SQL corpora. The current architecture is appropriate for supervised analyst use (engineer reviews generated SQL before execution) but not for fully automated analytical reporting pipelines where SQL correctness cannot be verified by a human in the loop.'),
    bullet('L3 — Simulated approval latency: the 27.6-second median approval time is a researcher self-timing estimate and likely underestimates real operator review time for complex multi-file diffs, particularly for engineers new to the affected pipeline\'s codebase. A formal user study (recommended in F4 below) is required to replace this estimate with validated measurements.'),
    bullet('L4 — Single deployment environment: all experiments ran on a single developer workstation via Docker Compose with sub-millisecond local inter-service latency. Production cloud deployments (Kubernetes, managed PostgreSQL, ChromaDB cloud) would introduce higher inter-service network latency, increasing the non-LLM components of MTTR above the 134-second observed mean.'),
    sp(80),

    h2('6.4  Future Work'),
    bullet('F1 — Kafka streaming detection: replace the current 15-second batch-polling MonitoringAgent with a real-time Kafka consumer processing pipeline_run events at source production. This reduces detection latency from ~15 s to sub-2 s, enabling OrchestrAI to intercept NULL_SPIKE and ZERO_LOAD failures before any downstream ML models are scored on corrupted feature data.'),
    bullet('F2 — GitHub Actions PR-based deployment: replace direct Python exec() fix application with GitHub Pull Request submission with automated CI checks (pytest + linting + integration tests) as required merge conditions. This provides cryptographically signed audit trails in version control, enables peer review for complex fixes, and allows automatic rollback via git revert on CI regression detection after merge.'),
    bullet('F3 — Enterprise multi-tenancy and RBAC: add row-level PostgreSQL security for tenant isolation, role-based access control (Admin/Analyst/Viewer RBAC), and SAML 2.0 SSO with Okta and Azure AD as prerequisites for commercial SaaS deployment. The existing FastAPI middleware architecture supports tenant-ID header injection with additive changes rather than architectural restructuring.'),
    bullet('F4 — Operator user study: a formal cognitive walkthrough with NASA-TLX task load index assessment across 10–15 real on-call data engineers would replace the researcher-simulated 27.6-second approval latency estimate with validated measurements and provide construct validity evidence for the HITL approval workflow design.'),
    bullet('F5 — Production ML retraining pipeline: implement a scheduled Airflow DAG extracting the last 90 days of real pipeline_run records from healing_outcomes, applying semi-automatic weak labelling using current model predictions with manual review of low-confidence classifications, retraining both pkl models, evaluating against a temporal hold-out set, and hot-swapping the backend pkl files without service interruption.'),
    sp(80),
    p('All six research objectives are fully met, all five quantitative targets exceeded, and the Design Science Research cycle is complete from problem relevance through artifact construction to rigorous experimental evaluation. OrchestrAI represents a novel, empirically validated contribution to the autonomous data reliability domain — demonstrating that coordinated multi-agent AI orchestration, combining ML-based detection, LLM-based reasoning, RAG-based institutional memory, and human-in-the-loop governance, is ready to transform reactive pipeline operations into proactive, self-healing infrastructure at enterprise scale.'),
  ];
}

// ══════════════════════════════════════════════════════════════════════════════
// REFERENCES
// ══════════════════════════════════════════════════════════════════════════════
function references() {
  function ref(num, text) {
    return new Paragraph({
      children: [new TextRun({ text: `[${num}]  ${text}`, size: 20, font: 'Times New Roman', color: '111111' })],
      indent: { left: 480, hanging: 480 },
      spacing: { after: 80, line: 280, lineRule: LineRuleType.AUTO },
    });
  }
  return [
    h1('REFERENCES', false),
    ref(1,  'Sculley, D., Holt, G., Golovin, D., Davydov, E., Phillips, T., Ebner, D., Chaudhary, V., Young, M., Crespo, J.-F., and Dennison, D. (2015). Hidden technical debt in machine learning systems. NeurIPS 2015, Vol. 28, pp. 2503–2511.'),
    ref(2,  'Amershi, S., Begel, A., Bird, C., DeLine, R., Gall, H., Kamar, E., Nagappan, N., Nushi, B., and Zimmermann, T. (2019). Software engineering for machine learning: A case study. ICSE-SEIP 2019, pp. 291–300. DOI: 10.1109/ICSE-SEIP.2019.00042.'),
    ref(3,  'LangChain AI (2024). LangGraph: A library for building stateful, multi-actor applications with LLMs [Software]. v0.4.8. https://github.com/langchain-ai/langgraph. Accessed: July 2026.'),
    ref(4,  'Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., and Kiela, D. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. NeurIPS 2020, Vol. 33, pp. 9459–9474.'),
    ref(5,  'Chandola, V., Banerjee, A., and Kumar, V. (2009). Anomaly detection: A survey. ACM Computing Surveys, 41(3), Art. 15. DOI: 10.1145/1541880.1541882.'),
    ref(6,  'Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., and Cao, Y. (2023). ReAct: Synergizing reasoning and acting in language models. ICLR 2023. https://openreview.net/forum?id=WE_vluYUL-X.'),
    ref(7,  'Seshia, S. A., Sadigh, D., and Sastry, S. S. (2018). Towards verified artificial intelligence. Commun. ACM, 61(7), pp. 46–55. DOI: 10.1145/3188745.3188776.'),
    ref(8,  'Kleppmann, M. (2017). Designing Data-Intensive Applications. O\'Reilly Media, Sebastopol, CA. ISBN: 978-1-4493-7332-0.'),
    ref(9,  'Guo, T., Chen, X., Wang, Y., Chang, R., Peng, S., Chawla, N. V., Wiest, O., and Zhang, X. (2024). Large language model based multi-agents: A survey. arXiv:2402.01680. https://arxiv.org/abs/2402.01680.'),
    ref(10, 'Hevner, A. R., March, S. T., Park, J., and Ram, S. (2004). Design science in information systems research. MIS Quarterly, 28(1), pp. 75–105. DOI: 10.2307/25148625.'),
  ];
}

module.exports = { chapter5, chapter6, references };
