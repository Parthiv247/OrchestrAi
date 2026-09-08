/**
 * Demo data — used when backend is unreachable.
 * Pages fall back to this so the portfolio always looks live.
 */

export const DEMO_PIPELINES = [
  {
    id: 'demo-1', name: 'PostgreSQL → Snowflake', dag_id: 'pipeline_postgresql_to_snowflake',
    source_type: 'postgresql', status: 'active', schedule: '0 */6 * * *',
    last_run: { id: 'r1', status: 'success', records_loaded: 48320, records_failed: 0, duration_seconds: 142, started_at: new Date(Date.now() - 3600000).toISOString(), log: '' },
  },
  {
    id: 'demo-2', name: 'REST API → Snowflake', dag_id: 'pipeline_rest_api_to_snowflake',
    source_type: 'rest_api', status: 'active', schedule: '*/30 * * * *',
    last_run: { id: 'r2', status: 'success', records_loaded: 8910, records_failed: 12, duration_seconds: 38, started_at: new Date(Date.now() - 1800000).toISOString(), log: '' },
  },
  {
    id: 'demo-3', name: 'CSV Files → Data Warehouse', dag_id: 'pipeline_csv_to_snowflake',
    source_type: 'csv', status: 'active', schedule: '0 2 * * *',
    last_run: { id: 'r3', status: 'failed', records_loaded: 0, records_failed: 5000, duration_seconds: 21, started_at: new Date(Date.now() - 7200000).toISOString(), log: 'Connection timeout after 20s' },
  },
  {
    id: 'demo-4', name: 'Google Sheets → PostgreSQL', dag_id: 'pipeline_google_sheets_to_snowflake',
    source_type: 'google_sheets', status: 'active', schedule: '0 */12 * * *',
    last_run: { id: 'r4', status: 'success', records_loaded: 1204, records_failed: 0, duration_seconds: 9, started_at: new Date(Date.now() - 43200000).toISOString(), log: '' },
  },
]

export const DEMO_INCIDENTS = [
  {
    id: 'inc-1', pipeline_id: 'demo-3', pipeline_name: 'CSV Files → Data Warehouse',
    anomaly_type: 'CONSECUTIVE_FAILURES', severity: 'high', status: 'open',
    detected_at: new Date(Date.now() - 7200000).toISOString(),
    root_cause: 'IsolationForest detected 3 consecutive failures — likely source schema drift or network timeout.',
    approval_status: 'pending', approval_token: 'tok-demo-1',
    suggested_fix: 'restart_pipeline',
  },
  {
    id: 'inc-2', pipeline_id: 'demo-2', pipeline_name: 'REST API → Snowflake',
    anomaly_type: 'ROW_COUNT_DROP', severity: 'medium', status: 'healing',
    detected_at: new Date(Date.now() - 1800000).toISOString(),
    root_cause: 'Row count dropped 89% vs 7-day baseline. API rate-limiting detected.',
    approval_status: 'approved', approval_token: 'tok-demo-2',
    suggested_fix: 'backfill_missing',
  },
  {
    id: 'inc-3', pipeline_id: 'demo-1', pipeline_name: 'PostgreSQL → Snowflake',
    anomaly_type: 'NULL_SPIKE', severity: 'low', status: 'resolved',
    detected_at: new Date(Date.now() - 86400000).toISOString(),
    root_cause: 'Null spike in email column — upstream app deployed with nullable field change.',
    approval_status: 'approved', approval_token: 'tok-demo-3',
    suggested_fix: 'add_null_check_rule',
  },
]

export const DEMO_STATS = {
  total_pipelines: 4,
  active_pipelines: 3,
  total_incidents: 3,
  open_incidents: 1,
  avg_mttr_seconds: 252,   // 4.2 min
  healing_success_rate: 0.94,
  total_records_loaded: 168320,
  query_success_rate: 0.967,
  nl_sql_accuracy: 0.67,
  cost_savings_pct: 0.34,
}

export const DEMO_HEALING_OUTCOMES = [
  { strategy: 'restart_pipeline', success: true, mttr_seconds: 180 },
  { strategy: 'backfill_missing', success: true, mttr_seconds: 420 },
  { strategy: 'reindex_table',    success: true, mttr_seconds: 95 },
  { strategy: 'restart_pipeline', success: false, mttr_seconds: 600 },
  { strategy: 'scale_resources',  success: true, mttr_seconds: 300 },
]

export const DEMO_QUERY_HISTORY = [
  { id: 'q1', question: 'How many orders were placed last week?', sql: 'SELECT COUNT(*) FROM raw.ecommerce_orders WHERE created_at >= NOW() - INTERVAL \'7 days\'', result_count: 1, created_at: new Date(Date.now() - 3600000).toISOString() },
  { id: 'q2', question: 'Top 5 products by revenue this month', sql: 'SELECT product_name, SUM(price * quantity) AS revenue FROM raw.ecommerce_orders WHERE DATE_TRUNC(\'month\', created_at) = DATE_TRUNC(\'month\', NOW()) GROUP BY product_name ORDER BY revenue DESC LIMIT 5', result_count: 5, created_at: new Date(Date.now() - 7200000).toISOString() },
  { id: 'q3', question: 'Average order value by customer segment', sql: 'SELECT customer_segment, ROUND(AVG(total_amount), 2) AS avg_order_value FROM raw.ecommerce_orders GROUP BY customer_segment ORDER BY avg_order_value DESC', result_count: 4, created_at: new Date(Date.now() - 86400000).toISOString() },
]

export const IS_DEMO = true

// ── Observability demo data ────────────────────────────────────────────────────
export const DEMO_INSIGHTS = [
  { id: 'i1', type: 'anomaly', severity: 'high', title: 'Throughput spike on pipeline_csv_to_snowflake', description: 'IsolationForest scored 0.92 anomaly. Records processed jumped 340% vs baseline.', pipeline_id: 'demo-3', created_at: new Date(Date.now() - 3600000).toISOString() },
  { id: 'i2', type: 'warning', severity: 'medium', title: 'API rate-limit approaching on REST API → Snowflake', description: '87% of rate quota consumed. Auto-backoff engaged.', pipeline_id: 'demo-2', created_at: new Date(Date.now() - 7200000).toISOString() },
  { id: 'i3', type: 'opportunity', severity: 'low', title: 'PostgreSQL → Snowflake can save ~$0.12/day', description: 'Query pushdown not enabled. Enabling reduces Snowflake credit usage.', pipeline_id: 'demo-1', created_at: new Date(Date.now() - 14400000).toISOString() },
  { id: 'i4', type: 'info', severity: 'low', title: 'Healing model retrained with 5 new samples', description: 'GradientBoosting accuracy improved from 0.81 → 0.88 after latest incident batch.', pipeline_id: null, created_at: new Date(Date.now() - 86400000).toISOString() },
]

export const DEMO_LEARNING_STATS = {
  total_samples: 47, model_accuracy: 0.88, last_trained_at: new Date(Date.now() - 86400000).toISOString(),
  feature_importances: [
    { feature: 'consecutive_failures', importance: 0.34 },
    { feature: 'row_count_delta_pct', importance: 0.27 },
    { feature: 'null_spike_pct', importance: 0.19 },
    { feature: 'latency_p95', importance: 0.12 },
    { feature: 'time_of_day', importance: 0.08 },
  ],
}

const _days7 = Array.from({ length: 7 }, (_, i) => {
  const d = new Date(Date.now() - (6 - i) * 86400000)
  return d.toISOString().slice(0, 10)
})

export const DEMO_METRICS_HISTORY = {
  pipeline_records: _days7.flatMap(date => [
    { date, dag_id: 'pipeline_postgresql_to_snowflake', records: 40000 + Math.floor(Math.random() * 15000) },
    { date, dag_id: 'pipeline_rest_api_to_snowflake',   records: 7000  + Math.floor(Math.random() * 4000) },
    { date, dag_id: 'pipeline_csv_to_snowflake',        records: 12000 + Math.floor(Math.random() * 8000) },
    { date, dag_id: 'pipeline_google_sheets_to_snowflake', records: 1000 + Math.floor(Math.random() * 500) },
  ]),
  incidents_per_day: _days7.map(date => ({ date, count: Math.floor(Math.random() * 3) })),
}

export const DEMO_SLA_DATA = {
  overall: { sla_pct: 96.4, total_runs: 168, successful_runs: 162, p95_latency: 287, error_rate: 0.036 },
  sla_by_pipeline: [
    { dag_id: 'postgresql_to_snowflake', sla_pct: 98.2, total_runs: 56, successful_runs: 55, p95_latency: 142, error_rate: 0.018, success_rate: 0.982, p95_s: 142, sla_breaches: 1 },
    { dag_id: 'rest_api_to_snowflake',   sla_pct: 94.4, total_runs: 72, successful_runs: 68, p95_latency: 38,  error_rate: 0.056, success_rate: 0.944, p95_s: 38,  sla_breaches: 4 },
    { dag_id: 'csv_to_snowflake',        sla_pct: 92.9, total_runs: 14, successful_runs: 13, p95_latency: 21,  error_rate: 0.071, success_rate: 0.929, p95_s: 21,  sla_breaches: 1 },
    { dag_id: 'google_sheets_to_snowflake', sla_pct: 100, total_runs: 26, successful_runs: 26, p95_latency: 9, error_rate: 0, success_rate: 1.0, p95_s: 9, sla_breaches: 0 },
  ],
  daily_timeline: _days7.map((date, i) => ({
    date,
    postgresql_to_snowflake: 95 + i,
    rest_api_to_snowflake: 88 + i * 1.2,
    csv_to_snowflake: 90 + i,
    google_sheets_to_snowflake: 100,
  })),
}

export const DEMO_MTTR_TREND = [
  { week: 'W1', mttr_minutes: 42 }, { week: 'W2', mttr_minutes: 31 },
  { week: 'W3', mttr_minutes: 18 }, { week: 'W4', mttr_minutes: 10 },
  { week: 'W5', mttr_minutes: 7  }, { week: 'W6', mttr_minutes: 4.2 },
]

// ── Quality demo data ──────────────────────────────────────────────────────────
export const DEMO_QUALITY_SUMMARY = {
  table_count: 8, rule_count: 12, failing_rules: 2, open_drift_events: 1,
  avg_health_score: 84,
}

export const DEMO_QUALITY_TABLES = [
  { name: 'raw.ecommerce_orders', row_count: 284930, column_count: 18, null_pct: 2.1, health_score: 92, status: 'healthy' },
  { name: 'raw.customers',        row_count: 48210,  column_count: 12, null_pct: 0.8, health_score: 97, status: 'healthy' },
  { name: 'raw.api_events',       row_count: 1240000, column_count: 9, null_pct: 14.2, health_score: 61, status: 'warning' },
  { name: 'raw.csv_uploads',      row_count: 5000,   column_count: 6,  null_pct: 31.0, health_score: 42, status: 'critical' },
  { name: 'staging.orders_clean', row_count: 282100, column_count: 20, null_pct: 0.4, health_score: 96, status: 'healthy' },
  { name: 'staging.customers',    row_count: 48100,  column_count: 14, null_pct: 0.2, health_score: 98, status: 'healthy' },
  { name: 'mart.revenue_daily',   row_count: 365,    column_count: 8,  null_pct: 0.0, health_score: 100, status: 'healthy' },
  { name: 'mart.customer_ltv',    row_count: 48100,  column_count: 11, null_pct: 1.2, health_score: 88, status: 'healthy' },
]

export const DEMO_QUALITY_RULES = [
  { id: 'r1', name: 'No nulls in order_id', description: 'Primary key must never be null', table_name: 'raw.ecommerce_orders', column_name: 'order_id', rule_type: 'not_null', condition: 'IS NOT NULL', threshold: 0, severity: 'critical', enabled: true, last_run_at: new Date(Date.now() - 1800000).toISOString(), last_status: 'pass', last_message: 'All 284930 rows pass' },
  { id: 'r2', name: 'Null % < 5% on email', description: 'Email column should rarely be null', table_name: 'raw.customers', column_name: 'email', rule_type: 'null_threshold', condition: 'null_pct < 5', threshold: 5, severity: 'high', enabled: true, last_run_at: new Date(Date.now() - 3600000).toISOString(), last_status: 'pass', last_message: '0.8% null — within threshold' },
  { id: 'r3', name: 'API events null < 10%', description: 'High nulls indicate source schema drift', table_name: 'raw.api_events', column_name: 'user_id', rule_type: 'null_threshold', condition: 'null_pct < 10', threshold: 10, severity: 'medium', enabled: true, last_run_at: new Date(Date.now() - 900000).toISOString(), last_status: 'fail', last_message: '14.2% null — exceeds threshold of 10%' },
  { id: 'r4', name: 'CSV uploads completeness', description: 'Row count > 3000 after load', table_name: 'raw.csv_uploads', column_name: '', rule_type: 'row_count', condition: 'row_count > 3000', threshold: 3000, severity: 'high', enabled: true, last_run_at: new Date(Date.now() - 7200000).toISOString(), last_status: 'fail', last_message: '5000 rows but 31% null — data incomplete' },
]

export const DEMO_DRIFT_EVENTS = [
  { id: 'd1', table_name: 'raw.api_events', event_type: 'column_added', column_name: 'session_context', old_value: '', new_value: 'TEXT', detected_at: new Date(Date.now() - 86400000).toISOString(), resolved: false },
]

// ── Optimizer demo data ────────────────────────────────────────────────────────
export const DEMO_SAVINGS = {
  total_dollar_saved: 4.72,
  avg_improvement_percent: 38.4,
  total_queries_optimized: 23,
  breakdown: {
    analyst:      { total_saved: 1.84, query_count: 9,  avg_pct: 41.2 },
    'dbt:staging':{ total_saved: 1.20, query_count: 7,  avg_pct: 35.8 },
    'dbt:mart':   { total_saved: 0.96, query_count: 5,  avg_pct: 38.1 },
    manual:       { total_saved: 0.72, query_count: 2,  avg_pct: 28.5 },
  },
}

// ── dbt demo data ──────────────────────────────────────────────────────────────
export const DEMO_DBT_MODELS = [
  { id: 'm1', name: 'stg_orders',    schema_layer: 'staging', status: 'pass', last_run_at: new Date(Date.now() - 3600000).toISOString(),  rows_affected: 282100, duration_seconds: 14 },
  { id: 'm2', name: 'stg_customers', schema_layer: 'staging', status: 'pass', last_run_at: new Date(Date.now() - 3600000).toISOString(),  rows_affected: 48100,  duration_seconds: 8  },
  { id: 'm3', name: 'stg_api_events',schema_layer: 'staging', status: 'warn', last_run_at: new Date(Date.now() - 7200000).toISOString(),  rows_affected: 1240000,duration_seconds: 41 },
  { id: 'm4', name: 'revenue_daily', schema_layer: 'marts',   status: 'pass', last_run_at: new Date(Date.now() - 1800000).toISOString(),  rows_affected: 365,    duration_seconds: 6  },
  { id: 'm5', name: 'customer_ltv',  schema_layer: 'marts',   status: 'pass', last_run_at: new Date(Date.now() - 1800000).toISOString(),  rows_affected: 48100,  duration_seconds: 19 },
]

export const DEMO_DBT_RUNS = [
  { id: 'run-1', status: 'pass', started_at: new Date(Date.now() - 1800000).toISOString(), finished_at: new Date(Date.now() - 1800000 + 88000).toISOString(), models_passed: 5, models_failed: 0, models_skipped: 0, duration_seconds: 88, trigger: 'scheduled' },
  { id: 'run-2', status: 'warn', started_at: new Date(Date.now() - 7200000).toISOString(), finished_at: new Date(Date.now() - 7200000 + 95000).toISOString(), models_passed: 4, models_failed: 0, models_skipped: 1, duration_seconds: 95, trigger: 'manual'    },
  { id: 'run-3', status: 'pass', started_at: new Date(Date.now() - 86400000).toISOString(),finished_at: new Date(Date.now() - 86400000 + 82000).toISOString(),models_passed: 5, models_failed: 0, models_skipped: 0, duration_seconds: 82, trigger: 'scheduled' },
]

// ── Reports demo data ──────────────────────────────────────────────────────────
export const DEMO_REPORTS = [
  { id: 'rep-1', name: 'Daily Pipeline Summary', description: 'Throughput, failures, and MTTR for all pipelines', schedule: '0 8 * * *', format: 'html', recipients: ['parthiv9060@gmail.com'], enabled: true, created_at: new Date(Date.now() - 7 * 86400000).toISOString(), last_sent_at: new Date(Date.now() - 86400000).toISOString() },
  { id: 'rep-2', name: 'Weekly Quality Report', description: 'Data quality scores and drift events', schedule: '0 9 * * 1', format: 'pdf',  recipients: ['parthiv9060@gmail.com'], enabled: true, created_at: new Date(Date.now() - 14 * 86400000).toISOString(), last_sent_at: new Date(Date.now() - 7 * 86400000).toISOString() },
  { id: 'rep-3', name: 'Incident Digest',        description: 'All anomalies and healing outcomes', schedule: '0 7 * * *', format: 'html', recipients: ['parthiv9060@gmail.com'], enabled: false, created_at: new Date(Date.now() - 3 * 86400000).toISOString(), last_sent_at: null },
]

export const DEMO_DELIVERIES = [
  { id: 'del-1', report_id: 'rep-1', status: 'sent',   sent_at: new Date(Date.now() - 86400000).toISOString(),     error: null },
  { id: 'del-2', report_id: 'rep-2', status: 'sent',   sent_at: new Date(Date.now() - 7 * 86400000).toISOString(), error: null },
  { id: 'del-3', report_id: 'rep-1', status: 'failed', sent_at: new Date(Date.now() - 2 * 86400000).toISOString(), error: 'SMTP timeout' },
]
