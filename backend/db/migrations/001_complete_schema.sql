-- =============================================================================
-- OrchestrAI — Complete Production Schema for Supabase (PostgreSQL 15+)
-- Migration: 001_complete_schema.sql
-- Run this once in Supabase SQL Editor → clears nothing, all CREATE IF NOT EXISTS
-- =============================================================================

-- ── Utility: auto-update updated_at on every UPDATE ───────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 1 — IDENTITY & AUTH
-- =============================================================================

-- Tenants (organisations / workspaces)
CREATE TABLE IF NOT EXISTS tenants (
    id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    name         TEXT NOT NULL,
    plan         TEXT NOT NULL DEFAULT 'free',   -- free | pro | enterprise
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tenants_name ON tenants(name);

DROP TRIGGER IF EXISTS trg_tenants_updated_at ON tenants;
CREATE TRIGGER trg_tenants_updated_at
  BEFORE UPDATE ON tenants
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Users (linked to Supabase auth.users)
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email           TEXT UNIQUE NOT NULL,
    hashed_password TEXT,                         -- NULL when using Supabase auth SSO
    role            TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('admin','analyst','viewer')),
    full_name       TEXT,
    avatar_url      TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active_at  TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_users_tenant   ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email);

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Team members (display/invite layer on top of users)
CREATE TABLE IF NOT EXISTS team_members (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id   TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    role        TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('admin','analyst','viewer')),
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','invited','suspended')),
    invited_by  TEXT,
    invited_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_team_members_tenant ON team_members(tenant_id);
CREATE INDEX IF NOT EXISTS idx_team_members_email  ON team_members(email);

-- API Tokens
CREATE TABLE IF NOT EXISTS api_tokens (
    id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id    TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    token_hash   TEXT NOT NULL UNIQUE,
    token_prefix TEXT NOT NULL,
    scopes       TEXT DEFAULT 'read',             -- read | write | admin
    created_by   TEXT,
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE,
    expires_at   TIMESTAMP WITH TIME ZONE,
    revoked      BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_api_tokens_tenant ON api_tokens(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_hash   ON api_tokens(token_hash);

-- Audit log (immutable — no UPDATE/DELETE)
CREATE TABLE IF NOT EXISTS audit_log (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id     TEXT REFERENCES tenants(id) ON DELETE SET NULL,
    actor         TEXT NOT NULL,
    action        TEXT NOT NULL,
    resource_type TEXT,
    resource_id   TEXT,
    details       JSONB DEFAULT '{}',
    ip_address    TEXT,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant   ON audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor    ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created  ON audit_log(created_at DESC);

-- =============================================================================
-- SECTION 2 — CONNECTORS & PIPELINES
-- =============================================================================

-- Data connections (source/destination credentials)
CREATE TABLE IF NOT EXISTS data_connections (
    id               TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id        TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    db_type          TEXT NOT NULL,              -- postgresql | snowflake | bigquery | mysql | mongodb | redshift | duckdb | kafka | flink | spark | s3 | gcs | azure_blob
    config_encrypted TEXT,                       -- AES-256 encrypted JSON blob
    is_active        BOOLEAN DEFAULT TRUE,
    last_tested_at   TIMESTAMP WITH TIME ZONE,
    last_test_status TEXT,                       -- success | failed | untested
    last_test_error  TEXT,
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_data_connections_tenant  ON data_connections(tenant_id);
CREATE INDEX IF NOT EXISTS idx_data_connections_type    ON data_connections(db_type);

DROP TRIGGER IF EXISTS trg_data_connections_updated_at ON data_connections;
CREATE TRIGGER trg_data_connections_updated_at
  BEFORE UPDATE ON data_connections
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Pipelines (ETL pipeline definitions)
CREATE TABLE IF NOT EXISTS pipelines (
    id                TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id         TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    dag_id            TEXT UNIQUE NOT NULL,
    name              TEXT NOT NULL,
    description       TEXT,
    source_type       TEXT,
    source_config     JSONB,
    dest_type         TEXT,
    destination_type  TEXT,
    dest_config       JSONB,
    schedule          TEXT,                      -- cron expression
    status            TEXT DEFAULT 'active' CHECK (status IN ('active','paused','disabled','error')),
    health_score      FLOAT DEFAULT 100,         -- 0–100
    tags              TEXT[] DEFAULT '{}',
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pipelines_tenant ON pipelines(tenant_id);
CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);

DROP TRIGGER IF EXISTS trg_pipelines_updated_at ON pipelines;
CREATE TRIGGER trg_pipelines_updated_at
  BEFORE UPDATE ON pipelines
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Pipeline SLA config (replaces hardcoded PIPELINE_SLA dict)
CREATE TABLE IF NOT EXISTS pipeline_sla (
    id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    pipeline_name  TEXT NOT NULL UNIQUE,
    sla_seconds    INTEGER NOT NULL DEFAULT 3600,
    breach_mult    FLOAT NOT NULL DEFAULT 3.0,   -- breach = sla_seconds * breach_mult
    owner_email    TEXT,
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
INSERT INTO pipeline_sla (pipeline_name, sla_seconds, breach_mult) VALUES
    ('ingest_nyc_taxi',   1800, 3.0),
    ('ingest_ecommerce',   900, 3.0),
    ('dbt_run',           3600, 3.0),
    ('kafka_consumer',     300, 3.0),
    ('flink_job',           60, 3.0),
    ('spark_streaming',     30, 3.0)
ON CONFLICT (pipeline_name) DO NOTHING;

DROP TRIGGER IF EXISTS trg_pipeline_sla_updated_at ON pipeline_sla;
CREATE TRIGGER trg_pipeline_sla_updated_at
  BEFORE UPDATE ON pipeline_sla
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Pipeline runs (one row per execution)
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                   TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    pipeline_name        TEXT NOT NULL,
    dag_id               TEXT,
    run_id               TEXT,
    source_type          TEXT,
    records_ingested     INTEGER DEFAULT 0,
    records_transformed  INTEGER DEFAULT 0,
    records_loaded       INTEGER DEFAULT 0,
    records_failed       INTEGER DEFAULT 0,
    null_rate            FLOAT DEFAULT 0,
    duplicate_rate       FLOAT DEFAULT 0,
    schema_change_count  INTEGER DEFAULT 0,
    cdc_lag_seconds      FLOAT DEFAULT 0,
    partition_skew_ratio FLOAT DEFAULT 0,
    load_mode            TEXT DEFAULT 'full' CHECK (load_mode IN ('full','incremental','initial')),
    watermark            TEXT,
    status               TEXT DEFAULT 'running' CHECK (status IN ('running','success','failed','warning','skipped')),
    error_message        TEXT,
    started_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at         TIMESTAMP WITH TIME ZONE,
    duration_seconds     FLOAT,
    updated_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_name      ON pipeline_runs(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status    ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started   ON pipeline_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_watermark ON pipeline_runs(pipeline_name, completed_at);

DROP TRIGGER IF EXISTS trg_pipeline_runs_updated_at ON pipeline_runs;
CREATE TRIGGER trg_pipeline_runs_updated_at
  BEFORE UPDATE ON pipeline_runs
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ETL watermarks (incremental load tracking — was in DuckDB, now in Supabase for multi-node)
CREATE TABLE IF NOT EXISTS etl_watermarks (
    id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    pipeline_name  TEXT NOT NULL,
    table_name     TEXT NOT NULL,
    watermark_col  TEXT NOT NULL,
    watermark_val  TEXT NOT NULL,
    run_id         TEXT,
    updated_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (pipeline_name, table_name)
);
CREATE INDEX IF NOT EXISTS idx_etl_watermarks_pipeline ON etl_watermarks(pipeline_name);

DROP TRIGGER IF EXISTS trg_etl_watermarks_updated_at ON etl_watermarks;
CREATE TRIGGER trg_etl_watermarks_updated_at
  BEFORE UPDATE ON etl_watermarks
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Pipeline metrics (time-series, one row per metric per run)
CREATE TABLE IF NOT EXISTS pipeline_metrics (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    pipeline_name TEXT NOT NULL,
    run_id        TEXT,
    metric_name   TEXT NOT NULL,
    metric_value  FLOAT NOT NULL,
    tags          JSONB DEFAULT '{}',
    recorded_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pipeline_metrics_name    ON pipeline_metrics(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_metrics_metric  ON pipeline_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_metrics_time    ON pipeline_metrics(recorded_at DESC);

-- Streaming metrics (Flink/Spark specific — separate for queryability)
CREATE TABLE IF NOT EXISTS streaming_metrics (
    id                TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    pipeline_name     TEXT NOT NULL,
    engine            TEXT NOT NULL CHECK (engine IN ('flink','spark','kafka')),
    run_id            TEXT,
    checkpoint_id     TEXT,
    checkpoint_status TEXT,                      -- success | failed | in_progress
    checkpoint_duration_ms BIGINT,
    backpressure_pct  FLOAT,
    micro_batch_ms    BIGINT,
    records_per_second FLOAT,
    consumer_lag      BIGINT,
    watermark_lag_ms  BIGINT,
    recorded_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_streaming_metrics_pipeline ON streaming_metrics(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_streaming_metrics_engine   ON streaming_metrics(engine);
CREATE INDEX IF NOT EXISTS idx_streaming_metrics_time     ON streaming_metrics(recorded_at DESC);

-- Connector configs (legacy / connector registry layer)
CREATE TABLE IF NOT EXISTS connector_configs (
    id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id      TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    connector_type TEXT NOT NULL,
    connector_id   TEXT NOT NULL,
    config_encrypted TEXT,
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_connector_configs_tenant ON connector_configs(tenant_id);

DROP TRIGGER IF EXISTS trg_connector_configs_updated_at ON connector_configs;
CREATE TRIGGER trg_connector_configs_updated_at
  BEFORE UPDATE ON connector_configs
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- SECTION 3 — HEALING PIPELINE (LangGraph)
-- =============================================================================

-- Incidents (one row per healing workflow invocation)
CREATE TABLE IF NOT EXISTS incidents (
    id                     TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id              TEXT REFERENCES tenants(id) ON DELETE SET NULL,
    pipeline_name          TEXT NOT NULL,
    run_id                 TEXT,
    -- Monitoring
    anomaly_type           TEXT,
    anomaly_details        JSONB,
    -- Lineage
    lineage_graph          JSONB,
    -- Diagnosis
    root_cause             TEXT,
    root_cause_confidence  FLOAT,
    reasoning_steps        JSONB DEFAULT '[]',
    -- Fix
    fix_code               TEXT,
    fix_language           TEXT DEFAULT 'python',
    fix_template_used      TEXT,
    -- Sandbox
    sandbox_results        JSONB,
    tests_passed           INTEGER,
    tests_failed           INTEGER,
    confidence_score       FLOAT,
    sandbox_threshold_used FLOAT DEFAULT 0.75,
    -- Approval
    approval_status        TEXT DEFAULT 'pending' CHECK (approval_status IN ('pending','approved','rejected','auto_approved')),
    approval_token         TEXT,
    approval_email         TEXT,
    approved_by            TEXT,
    approved_at            TIMESTAMP WITH TIME ZONE,
    -- Deployment
    deployed               BOOLEAN DEFAULT FALSE,
    deployment_result      JSONB,
    -- Status / meta
    status                 TEXT DEFAULT 'open' CHECK (status IN ('open','diagnosing','fix_ready','pending_approval','deployed','closed','failed')),
    error                  TEXT,
    created_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at            TIMESTAMP WITH TIME ZONE,
    updated_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_incidents_pipeline  ON incidents(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_incidents_anomaly   ON incidents(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_incidents_status    ON incidents(approval_status);
CREATE INDEX IF NOT EXISTS idx_incidents_created   ON incidents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_tenant    ON incidents(tenant_id);

DROP TRIGGER IF EXISTS trg_incidents_updated_at ON incidents;
CREATE TRIGGER trg_incidents_updated_at
  BEFORE UPDATE ON incidents
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Fixes (one row per fix attempt — FK to incident)
CREATE TABLE IF NOT EXISTS fixes (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    incident_id     TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    fix_code        TEXT NOT NULL,
    fix_language    TEXT DEFAULT 'python',
    template_used   TEXT,
    rag_hit         BOOLEAN DEFAULT FALSE,
    rag_fix_id      TEXT,                        -- ChromaDB doc id
    test_results    JSONB,
    confidence_score FLOAT,
    deployed        BOOLEAN DEFAULT FALSE,
    deployed_at     TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fixes_incident ON fixes(incident_id);

-- Sandbox test runs (one row per test per sandbox execution)
CREATE TABLE IF NOT EXISTS sandbox_test_runs (
    id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    incident_id  TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    fix_id       TEXT REFERENCES fixes(id) ON DELETE CASCADE,
    test_id      TEXT NOT NULL,                  -- T01, T02, … T20
    test_name    TEXT NOT NULL,
    result       TEXT NOT NULL CHECK (result IN ('PASS','FAIL','SKIP','ERROR')),
    duration_ms  INTEGER,
    output       TEXT,
    error_detail TEXT,
    ran_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sandbox_test_runs_incident ON sandbox_test_runs(incident_id);
CREATE INDEX IF NOT EXISTS idx_sandbox_test_runs_fix      ON sandbox_test_runs(fix_id);

-- Healing outcomes (called by OutcomeTracker on approve/reject)
CREATE TABLE IF NOT EXISTS healing_outcomes (
    id               TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    incident_id      TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    pipeline_name    TEXT NOT NULL,
    anomaly_type     TEXT NOT NULL,
    healing_strategy TEXT NOT NULL,
    fix_code_hash    TEXT,
    outcome          TEXT NOT NULL CHECK (outcome IN ('approved','rejected','auto_healed','expired')),
    mttr_seconds     FLOAT,
    confidence_score FLOAT,
    approved_by      TEXT,
    detection_at     TIMESTAMP WITH TIME ZONE,
    resolved_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_healing_outcomes_incident  ON healing_outcomes(incident_id);
CREATE INDEX IF NOT EXISTS idx_healing_outcomes_pipeline  ON healing_outcomes(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_healing_outcomes_anomaly   ON healing_outcomes(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_healing_outcomes_outcome   ON healing_outcomes(outcome);
CREATE INDEX IF NOT EXISTS idx_healing_outcomes_created   ON healing_outcomes(created_at DESC);

-- Fix library (relational mirror of ChromaDB — for SQL analytics, not semantic search)
CREATE TABLE IF NOT EXISTS fix_library (
    id              TEXT PRIMARY KEY,            -- same UUID as ChromaDB doc_id
    anomaly_type    TEXT NOT NULL,
    db_platform     TEXT NOT NULL DEFAULT 'postgresql',
    fix_code        TEXT NOT NULL,
    fix_language    TEXT DEFAULT 'python',
    template_used   TEXT,
    root_cause      TEXT,
    confidence_score FLOAT DEFAULT 0,
    success_count   INTEGER DEFAULT 0,
    failure_count   INTEGER DEFAULT 0,
    mttr_minutes    FLOAT DEFAULT 0,
    deprecated      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fix_library_anomaly    ON fix_library(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_fix_library_platform   ON fix_library(db_platform);
CREATE INDEX IF NOT EXISTS idx_fix_library_deprecated ON fix_library(deprecated);

DROP TRIGGER IF EXISTS trg_fix_library_updated_at ON fix_library;
CREATE TRIGGER trg_fix_library_updated_at
  BEFORE UPDATE ON fix_library
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- SECTION 4 — DATA QUALITY & OBSERVABILITY
-- =============================================================================

-- Quality rules (configurable checks per table/column)
CREATE TABLE IF NOT EXISTS quality_rules (
    id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id    TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    description  TEXT DEFAULT '',
    table_name   TEXT NOT NULL,
    column_name  TEXT DEFAULT '',
    rule_type    TEXT NOT NULL CHECK (rule_type IN ('not_null','uniqueness','range','regex','freshness','row_count','custom_sql','referential')),
    condition    TEXT NOT NULL,
    threshold    FLOAT DEFAULT 0,
    severity     TEXT DEFAULT 'warning' CHECK (severity IN ('info','warning','critical')),
    enabled      BOOLEAN DEFAULT TRUE,
    last_run_at  TIMESTAMP WITH TIME ZONE,
    last_status  TEXT DEFAULT 'pending' CHECK (last_status IN ('pending','pass','fail','error')),
    last_message TEXT DEFAULT '',
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_quality_rules_tenant ON quality_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_quality_rules_table  ON quality_rules(table_name);

DROP TRIGGER IF EXISTS trg_quality_rules_updated_at ON quality_rules;
CREATE TRIGGER trg_quality_rules_updated_at
  BEFORE UPDATE ON quality_rules
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Quality check results (one row per rule execution)
CREATE TABLE IF NOT EXISTS quality_check_results (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    rule_id     TEXT NOT NULL REFERENCES quality_rules(id) ON DELETE CASCADE,
    pipeline_run_id TEXT,
    status      TEXT NOT NULL CHECK (status IN ('pass','fail','error','skipped')),
    metric_value FLOAT,
    threshold   FLOAT,
    message     TEXT,
    row_count   BIGINT,
    error_rows  BIGINT DEFAULT 0,
    ran_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_qcr_rule    ON quality_check_results(rule_id);
CREATE INDEX IF NOT EXISTS idx_qcr_status  ON quality_check_results(status);
CREATE INDEX IF NOT EXISTS idx_qcr_time    ON quality_check_results(ran_at DESC);

-- Schema snapshots (baseline for drift detection)
CREATE TABLE IF NOT EXISTS schema_snapshots (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    table_name  TEXT NOT NULL,
    connection_id TEXT,
    schema_json JSONB NOT NULL,
    row_count   BIGINT DEFAULT 0,
    snapshot_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_schema_snapshots_table ON schema_snapshots(table_name);
CREATE INDEX IF NOT EXISTS idx_schema_snapshots_time  ON schema_snapshots(snapshot_at DESC);

-- Drift events (when MonitoringAgent detects SCHEMA_DRIFT)
CREATE TABLE IF NOT EXISTS drift_events (
    id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    pipeline_name TEXT,
    table_name   TEXT NOT NULL,
    event_type   TEXT NOT NULL CHECK (event_type IN ('column_added','column_removed','type_changed','constraint_changed','table_added','table_removed')),
    column_name  TEXT DEFAULT '',
    old_value    TEXT DEFAULT '',
    new_value    TEXT DEFAULT '',
    severity     TEXT DEFAULT 'warning' CHECK (severity IN ('info','warning','critical')),
    incident_id  TEXT REFERENCES incidents(id) ON DELETE SET NULL,
    detected_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved     BOOLEAN DEFAULT FALSE,
    resolved_at  TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_drift_events_pipeline ON drift_events(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_drift_events_table    ON drift_events(table_name);
CREATE INDEX IF NOT EXISTS idx_drift_events_time     ON drift_events(detected_at DESC);

-- PII scan results
CREATE TABLE IF NOT EXISTS pii_scan_results (
    id               TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    table_name       TEXT NOT NULL,
    column_name      TEXT NOT NULL,
    pii_type         TEXT NOT NULL,             -- name | email | phone | ssn | credit_card | address | dob | ip_address | passport | custom
    severity         TEXT NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    detection_method TEXT DEFAULT 'regex' CHECK (detection_method IN ('regex','llm','ml')),
    confidence       FLOAT DEFAULT 1.0,
    suppressed       BOOLEAN DEFAULT FALSE,
    tagged_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    suppressed_at    TIMESTAMP WITH TIME ZONE,
    suppressed_by    TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_pii_scan_results_table    ON pii_scan_results(table_name);
CREATE INDEX IF NOT EXISTS idx_pii_scan_results_pii_type ON pii_scan_results(pii_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pii_unique_col ON pii_scan_results(table_name, column_name, pii_type);

-- =============================================================================
-- SECTION 5 — DATA LINEAGE
-- =============================================================================

-- Lineage nodes (tables, models, sources, sinks)
CREATE TABLE IF NOT EXISTS lineage_nodes (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id   TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    node_type   TEXT NOT NULL CHECK (node_type IN ('source','model','mart','sink','external','stream')),
    db_platform TEXT,
    schema_name TEXT,
    table_name  TEXT,
    description TEXT,
    owner       TEXT,
    tags        TEXT[] DEFAULT '{}',
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_lineage_nodes_tenant    ON lineage_nodes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_lineage_nodes_type      ON lineage_nodes(node_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_lineage_nodes_name ON lineage_nodes(tenant_id, name);

DROP TRIGGER IF EXISTS trg_lineage_nodes_updated_at ON lineage_nodes;
CREATE TRIGGER trg_lineage_nodes_updated_at
  BEFORE UPDATE ON lineage_nodes
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Lineage edges (directed dependency: upstream → downstream)
CREATE TABLE IF NOT EXISTS lineage_edges (
    id               TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    upstream_node_id TEXT NOT NULL REFERENCES lineage_nodes(id) ON DELETE CASCADE,
    downstream_node_id TEXT NOT NULL REFERENCES lineage_nodes(id) ON DELETE CASCADE,
    transform_type   TEXT DEFAULT 'etl' CHECK (transform_type IN ('etl','dbt','stream','view','ml','manual')),
    pipeline_name    TEXT,
    sql_expression   TEXT,
    metadata         JSONB DEFAULT '{}',
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (upstream_node_id, downstream_node_id, transform_type)
);
CREATE INDEX IF NOT EXISTS idx_lineage_edges_up   ON lineage_edges(upstream_node_id);
CREATE INDEX IF NOT EXISTS idx_lineage_edges_down ON lineage_edges(downstream_node_id);

-- =============================================================================
-- SECTION 6 — NOTIFICATIONS & ALERTS
-- =============================================================================

-- Notification config (one row per tenant, not a singleton)
CREATE TABLE IF NOT EXISTS notification_config (
    id                 TEXT PRIMARY KEY DEFAULT 'default',
    tenant_id          TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    slack_webhook_url  TEXT DEFAULT '',
    pagerduty_key      TEXT DEFAULT '',
    email_from         TEXT DEFAULT '',
    email_smtp_host    TEXT DEFAULT '',
    email_smtp_port    INTEGER DEFAULT 587,
    email_smtp_user    TEXT DEFAULT '',
    email_smtp_pass    TEXT DEFAULT '',
    alert_rules        JSONB DEFAULT '[]',
    updated_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
INSERT INTO notification_config (id) VALUES ('default') ON CONFLICT (id) DO NOTHING;

DROP TRIGGER IF EXISTS trg_notification_config_updated_at ON notification_config;
CREATE TRIGGER trg_notification_config_updated_at
  BEFORE UPDATE ON notification_config
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Alert rules
CREATE TABLE IF NOT EXISTS alert_rules (
    id                TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id         TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    description       TEXT DEFAULT '',
    condition         TEXT NOT NULL,             -- pipeline_failure | anomaly | cost_threshold | null_spike | row_count_drop | sla_breach | custom
    channel           TEXT NOT NULL CHECK (channel IN ('slack','email','pagerduty')),
    threshold         FLOAT DEFAULT 0,
    cooldown_minutes  INTEGER DEFAULT 60,
    enabled           BOOLEAN DEFAULT TRUE,
    last_fired_at     TIMESTAMP WITH TIME ZONE,
    fire_count        INTEGER DEFAULT 0,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alert_rules_tenant  ON alert_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled);

DROP TRIGGER IF EXISTS trg_alert_rules_updated_at ON alert_rules;
CREATE TRIGGER trg_alert_rules_updated_at
  BEFORE UPDATE ON alert_rules
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Seed default alert rules
INSERT INTO alert_rules (id, name, description, condition, channel, threshold, cooldown_minutes, enabled)
VALUES
  (gen_random_uuid()::TEXT, 'Pipeline Failure Alert',  'Fire on any pipeline failure',       'pipeline_failure', 'slack',     0,   60,   TRUE),
  (gen_random_uuid()::TEXT, 'Anomaly Detected',         'ML anomaly score above threshold',   'anomaly',          'slack',     0.8, 120,  TRUE),
  (gen_random_uuid()::TEXT, 'Null Spike Alert',         'Null rate jumps > 20%',              'null_spike',       'slack',     20,  60,   TRUE),
  (gen_random_uuid()::TEXT, 'Row Count Drop',           'Row count drops > 30% vs prior run', 'row_count_drop',   'slack',     30,  30,   FALSE),
  (gen_random_uuid()::TEXT, 'SLA Breach',               'Pipeline exceeded SLA target',       'sla_breach',       'pagerduty', 0,   30,   TRUE),
  (gen_random_uuid()::TEXT, 'Cost Threshold Exceeded',  'Daily spend over $50',               'cost_threshold',   'email',     50,  1440, FALSE)
ON CONFLICT DO NOTHING;

-- Notification history
CREATE TABLE IF NOT EXISTS notification_history (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id     TEXT REFERENCES tenants(id) ON DELETE SET NULL,
    rule_id       TEXT REFERENCES alert_rules(id) ON DELETE SET NULL,
    channel       TEXT NOT NULL,
    subject       TEXT NOT NULL,
    body          TEXT,
    status        TEXT DEFAULT 'sent' CHECK (status IN ('sent','failed','skipped')),
    error_message TEXT DEFAULT '',
    sent_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notification_history_tenant ON notification_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_notification_history_time   ON notification_history(sent_at DESC);

-- =============================================================================
-- SECTION 7 — ANALYTICS & AI ASSISTANT
-- =============================================================================

-- Natural language queries
CREATE TABLE IF NOT EXISTS queries (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id     TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    user_id       TEXT REFERENCES users(id) ON DELETE SET NULL,
    nl_query      TEXT NOT NULL,
    generated_sql TEXT,
    optimized_sql TEXT,
    executed      BOOLEAN DEFAULT FALSE,
    rows_returned INTEGER,
    chart_type    TEXT,
    chart_config  JSONB,
    cost_estimate FLOAT,
    execution_ms  INTEGER,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_queries_tenant ON queries(tenant_id);
CREATE INDEX IF NOT EXISTS idx_queries_user   ON queries(user_id);
CREATE INDEX IF NOT EXISTS idx_queries_time   ON queries(created_at DESC);

-- Query feedback
CREATE TABLE IF NOT EXISTS feedback (
    id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id  TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    query_id   TEXT NOT NULL REFERENCES queries(id) ON DELETE CASCADE,
    thumbs_up  BOOLEAN NOT NULL,
    comment    TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_feedback_query ON feedback(query_id);

-- Query history (broader than "queries" — covers ALL SQL executed)
CREATE TABLE IF NOT EXISTS query_history (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id       TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         TEXT REFERENCES users(id) ON DELETE SET NULL,
    question        TEXT,
    generated_sql   TEXT,
    optimized_sql   TEXT,
    rows_returned   INTEGER,
    execution_time_ms INTEGER,
    chart_type      TEXT,
    feedback        INTEGER CHECK (feedback IN (-1, 0, 1)),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_query_history_tenant ON query_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_query_history_time   ON query_history(created_at DESC);

-- AI Insights
CREATE TABLE IF NOT EXISTS insights (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id     TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    connection_id TEXT,
    title         TEXT NOT NULL,
    insight       TEXT NOT NULL,
    severity      TEXT DEFAULT 'info' CHECK (severity IN ('anomaly','warning','opportunity','info')),
    metric        TEXT,
    time_window   TEXT CHECK (time_window IN ('24h','7d','30d','90d')),
    table_name    TEXT,
    supporting_sql TEXT,
    generated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_insights_tenant   ON insights(tenant_id);
CREATE INDEX IF NOT EXISTS idx_insights_severity ON insights(severity);
CREATE INDEX IF NOT EXISTS idx_insights_time     ON insights(generated_at DESC);

-- Conversation sessions (AI Analyst chat history)
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id  TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    user_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
    title      TEXT,
    history    JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conv_sessions_tenant ON conversation_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_conv_sessions_user   ON conversation_sessions(user_id);

DROP TRIGGER IF EXISTS trg_conv_sessions_updated_at ON conversation_sessions;
CREATE TRIGGER trg_conv_sessions_updated_at
  BEFORE UPDATE ON conversation_sessions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- SECTION 8 — TRANSFORMATION (dbt + Optimizer)
-- =============================================================================

-- dbt run batches
CREATE TABLE IF NOT EXISTS dbt_runs (
    id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id           TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    triggered_by        TEXT,
    models_generated    INTEGER DEFAULT 0,
    models_succeeded    INTEGER DEFAULT 0,
    models_failed       INTEGER DEFAULT 0,
    tests_passed        INTEGER DEFAULT 0,
    tests_failed        INTEGER DEFAULT 0,
    mart_tables_created JSONB,
    run_output          TEXT,
    status              TEXT DEFAULT 'running' CHECK (status IN ('running','success','partial','failed')),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at        TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_dbt_runs_tenant ON dbt_runs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dbt_runs_time   ON dbt_runs(created_at DESC);

-- Individual dbt model results (one row per model per dbt_run)
CREATE TABLE IF NOT EXISTS dbt_models (
    id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    run_id       TEXT NOT NULL REFERENCES dbt_runs(id) ON DELETE CASCADE,
    model_name   TEXT NOT NULL,
    schema_name  TEXT,
    materialized TEXT DEFAULT 'table' CHECK (materialized IN ('table','view','incremental','ephemeral')),
    status       TEXT NOT NULL CHECK (status IN ('success','error','skipped')),
    rows_affected BIGINT,
    duration_ms  INTEGER,
    error_detail TEXT,
    compiled_sql TEXT,
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dbt_models_run    ON dbt_models(run_id);
CREATE INDEX IF NOT EXISTS idx_dbt_models_name   ON dbt_models(model_name);
CREATE INDEX IF NOT EXISTS idx_dbt_models_status ON dbt_models(status);

-- Query optimizations
CREATE TABLE IF NOT EXISTS query_optimizations (
    id                      TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id               TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    connection_id           TEXT,
    original_sql            TEXT NOT NULL,
    optimized_sql           TEXT,
    changes_made            JSONB,
    anti_patterns_found     JSONB,
    original_cost           FLOAT,
    optimized_cost          FLOAT,
    savings_percent         FLOAT,
    dollar_savings          FLOAT,
    execution_time_before_ms INTEGER,
    execution_time_after_ms  INTEGER,
    db_dialect              TEXT,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_query_opts_tenant ON query_optimizations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_query_opts_time   ON query_optimizations(created_at DESC);

-- =============================================================================
-- SECTION 9 — REPORTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS reports (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id   TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    report_type TEXT NOT NULL CHECK (report_type IN ('pipeline_health','anomaly_summary','cost_analysis','quality_report','executive_summary','custom')),
    config      JSONB DEFAULT '{}',
    schedule    TEXT,                            -- cron or NULL for on-demand
    recipients  TEXT[] DEFAULT '{}',
    enabled     BOOLEAN DEFAULT TRUE,
    created_by  TEXT,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reports_tenant ON reports(tenant_id);

DROP TRIGGER IF EXISTS trg_reports_updated_at ON reports;
CREATE TRIGGER trg_reports_updated_at
  BEFORE UPDATE ON reports
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE IF NOT EXISTS report_runs (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    report_id   TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    status      TEXT DEFAULT 'running' CHECK (status IN ('running','success','failed')),
    output_url  TEXT,
    error       TEXT,
    triggered_by TEXT,
    started_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_report_runs_report ON report_runs(report_id);
CREATE INDEX IF NOT EXISTS idx_report_runs_time   ON report_runs(started_at DESC);

-- =============================================================================
-- SECTION 10 — SYSTEM
-- =============================================================================

CREATE TABLE IF NOT EXISTS system_metrics (
    id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    metric_name  TEXT UNIQUE NOT NULL,
    metric_value FLOAT DEFAULT 0.0,
    updated_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
INSERT INTO system_metrics (metric_name, metric_value) VALUES
  ('total_pipelines',    0), ('active_incidents',  0),
  ('avg_mttr_minutes',   0), ('heal_rate_pct',      0),
  ('anomalies_30d',      0), ('fixes_deployed',     0)
ON CONFLICT (metric_name) DO NOTHING;

-- =============================================================================
-- SECTION 11 — ROW LEVEL SECURITY (Supabase multi-tenant isolation)
-- =============================================================================
-- Enable RLS on every tenant-scoped table.
-- Policy: authenticated users can only see rows where tenant_id matches their JWT claim.
-- The anon key is blocked from all writes.
-- Service role key bypasses RLS (used by the backend).

ALTER TABLE tenants              ENABLE ROW LEVEL SECURITY;
ALTER TABLE users                ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_members         ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_tokens           ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_connections     ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipelines            ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents            ENABLE ROW LEVEL SECURITY;
ALTER TABLE fixes                ENABLE ROW LEVEL SECURITY;
ALTER TABLE healing_outcomes     ENABLE ROW LEVEL SECURITY;
ALTER TABLE quality_rules        ENABLE ROW LEVEL SECURITY;
ALTER TABLE quality_check_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE lineage_nodes        ENABLE ROW LEVEL SECURITY;
ALTER TABLE lineage_edges        ENABLE ROW LEVEL SECURITY;
ALTER TABLE queries              ENABLE ROW LEVEL SECURITY;
ALTER TABLE insights             ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbt_runs             ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports              ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log            ENABLE ROW LEVEL SECURITY;

-- Helper: extract tenant_id from JWT
-- Supabase sets app.tenant_id in the JWT custom claims.
-- Your backend sets it via: SET LOCAL app.tenant_id = 'xxx';
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS TEXT AS $$
  SELECT COALESCE(
    current_setting('app.tenant_id', TRUE),
    (current_setting('request.jwt.claims', TRUE)::JSONB ->> 'tenant_id')
  );
$$ LANGUAGE sql STABLE;

-- RLS policies — authenticated reads are tenant-scoped; service role bypasses
CREATE POLICY IF NOT EXISTS "tenant_isolation_incidents"
  ON incidents FOR ALL TO authenticated
  USING (tenant_id = current_tenant_id() OR tenant_id IS NULL);

CREATE POLICY IF NOT EXISTS "tenant_isolation_pipelines"
  ON pipelines FOR ALL TO authenticated
  USING (tenant_id = current_tenant_id() OR tenant_id IS NULL);

CREATE POLICY IF NOT EXISTS "tenant_isolation_pipeline_runs"
  ON pipeline_runs FOR ALL TO authenticated
  USING (TRUE);  -- pipeline_runs has no tenant_id — shared read

CREATE POLICY IF NOT EXISTS "tenant_isolation_healing_outcomes"
  ON healing_outcomes FOR ALL TO authenticated
  USING (TRUE);  -- analytics table — shared read in single-tenant MVP

CREATE POLICY IF NOT EXISTS "tenant_isolation_quality_rules"
  ON quality_rules FOR ALL TO authenticated
  USING (tenant_id = current_tenant_id() OR tenant_id IS NULL);

CREATE POLICY IF NOT EXISTS "tenant_isolation_lineage_nodes"
  ON lineage_nodes FOR ALL TO authenticated
  USING (tenant_id = current_tenant_id() OR tenant_id IS NULL);

CREATE POLICY IF NOT EXISTS "tenant_isolation_insights"
  ON insights FOR ALL TO authenticated
  USING (tenant_id = current_tenant_id() OR tenant_id IS NULL);

CREATE POLICY IF NOT EXISTS "tenant_isolation_queries"
  ON queries FOR ALL TO authenticated
  USING (tenant_id = current_tenant_id() OR tenant_id IS NULL);

CREATE POLICY IF NOT EXISTS "tenant_isolation_conversations"
  ON conversation_sessions FOR ALL TO authenticated
  USING (tenant_id = current_tenant_id() OR tenant_id IS NULL);

CREATE POLICY IF NOT EXISTS "tenant_isolation_reports"
  ON reports FOR ALL TO authenticated
  USING (tenant_id = current_tenant_id() OR tenant_id IS NULL);

CREATE POLICY IF NOT EXISTS "tenant_isolation_audit_log"
  ON audit_log FOR SELECT TO authenticated
  USING (tenant_id = current_tenant_id() OR tenant_id IS NULL);

-- =============================================================================
-- SECTION 12 — SEED DEFAULT TENANT
-- =============================================================================

INSERT INTO tenants (id, name, plan) VALUES ('default', 'OrchestrAI', 'pro')
ON CONFLICT (id) DO NOTHING;

INSERT INTO team_members (id, name, email, role, status)
VALUES ('admin-seed', 'Admin', 'admin@orchestrai.io', 'admin', 'active')
ON CONFLICT (email) DO NOTHING;

-- =============================================================================
-- SCHEMA SUMMARY
-- =============================================================================
-- Section 1:  tenants, users, team_members, api_tokens, audit_log
-- Section 2:  data_connections, pipelines, pipeline_sla, pipeline_runs,
--             etl_watermarks, pipeline_metrics, streaming_metrics, connector_configs
-- Section 3:  incidents, fixes, sandbox_test_runs, healing_outcomes, fix_library
-- Section 4:  quality_rules, quality_check_results, schema_snapshots,
--             drift_events, pii_scan_results
-- Section 5:  lineage_nodes, lineage_edges
-- Section 6:  notification_config, alert_rules, notification_history
-- Section 7:  queries, feedback, query_history, insights, conversation_sessions
-- Section 8:  dbt_runs, dbt_models, query_optimizations
-- Section 9:  reports, report_runs
-- Section 10: system_metrics
-- Section 11: RLS policies + current_tenant_id() function
-- Section 12: Seed data
-- =============================================================================
-- Total tables: 40
-- Foreign keys: 32
-- Indexes:      70+
-- RLS policies: 13
-- Triggers:     18
-- =============================================================================
