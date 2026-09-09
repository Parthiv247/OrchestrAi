"""SQLAlchemy models for OrchestrAI — complete schema (all 40 tables)."""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, Float, Text, JSON, ARRAY,
    DateTime, ForeignKey, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship, DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


class RoleEnum(str, enum.Enum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class IncidentStatusEnum(str, enum.Enum):
    open = "open"
    diagnosing = "diagnosing"
    fix_ready = "fix_ready"
    pending_approval = "pending_approval"
    deployed = "deployed"
    closed = "closed"


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    users = relationship("User", back_populates="tenant")
    queries = relationship("Query", back_populates="tenant")
    incidents = relationship("Incident", back_populates="tenant")


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(RoleEnum), default=RoleEnum.viewer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    tenant = relationship("Tenant", back_populates="users")
    queries = relationship("Query", back_populates="user")


class Query(Base):
    __tablename__ = "queries"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    nl_query = Column(Text, nullable=False)
    generated_sql = Column(Text)
    executed = Column(Boolean, default=False)
    cost_estimate = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    tenant = relationship("Tenant", back_populates="queries")
    user = relationship("User", back_populates="queries")
    feedback = relationship("Feedback", back_populates="query")


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True)
    pipeline_name = Column(String(255), nullable=False)
    run_id = Column(String(255), nullable=True)

    # Monitoring
    anomaly_type = Column(String(255))
    anomaly_details = Column(JSON, nullable=True)

    # Lineage
    lineage_graph = Column(JSON, nullable=True)

    # Diagnosis
    root_cause = Column(Text)
    root_cause_confidence = Column(Float, nullable=True)

    # Fix
    fix_code = Column(Text)
    fix_language = Column(String(50), nullable=True)

    # Sandbox
    sandbox_results = Column(JSON, nullable=True)
    tests_passed = Column(Integer, nullable=True)
    tests_failed = Column(Integer, nullable=True)
    confidence_score = Column(Float, nullable=True)

    # Approval
    approval_status = Column(String(50), default="pending")
    approval_token = Column(String(255), nullable=True)
    approval_email = Column(String(255), nullable=True)
    approved_by = Column(String, nullable=True)

    # Deployment
    deployed = Column(Boolean, default=False)
    deployment_result = Column(JSON, nullable=True)

    # Legacy / status enum
    status = Column(SAEnum(IncidentStatusEnum), default=IncidentStatusEnum.open)
    sandbox_passed = Column(Boolean, default=False)

    # Meta
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="incidents", foreign_keys=[tenant_id])
    fixes = relationship("Fix", back_populates="incident")


class Fix(Base):
    __tablename__ = "fixes"
    id = Column(String, primary_key=True)
    incident_id = Column(String, ForeignKey("incidents.id"), nullable=False)
    fix_code = Column(Text, nullable=False)
    test_results = Column(Text)
    confidence_score = Column(Float)
    deployed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    incident = relationship("Incident", back_populates="fixes")


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    query_id = Column(String, ForeignKey("queries.id"), nullable=False)
    thumbs_up = Column(Boolean, nullable=False)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    query = relationship("Query", back_populates="feedback")


# ── Phase 1: ETL Pipeline Foundation ──────────────────────────────────────────

class DataConnection(Base):
    __tablename__ = "data_connections"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=True)
    name = Column(String(255), nullable=False, unique=True)
    db_type = Column(String(100), nullable=False)
    config_encrypted = Column(Text)
    is_active = Column(Boolean, default=True)
    last_tested_at = Column(DateTime, nullable=True)
    last_test_status = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Pipeline(Base):
    __tablename__ = "pipelines"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=True)
    dag_id = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(String(100))
    source_config = Column(JSON)
    dest_type = Column(String(100))
    dest_config = Column(JSON)
    destination_type = Column(String(100), nullable=True)
    schedule = Column(String(100))
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id = Column(String, primary_key=True)
    pipeline_name = Column(String(255))
    dag_id = Column(String(255), nullable=True)
    run_id = Column(String(255))
    records_ingested = Column(Integer, default=0)
    records_transformed = Column(Integer, default=0)
    records_loaded = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    status = Column(String(50), default="running")
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)


class PipelineMetric(Base):
    __tablename__ = "pipeline_metrics"
    id = Column(String, primary_key=True)
    pipeline_name = Column(String(255))
    metric_name = Column(String(255))
    metric_value = Column(Float)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class ConnectorConfig(Base):
    __tablename__ = "connector_configs"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=True)
    name = Column(String(255), nullable=False)
    connector_type = Column(String(50), nullable=False)
    connector_id = Column(String(100), nullable=False)
    config_encrypted = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Phase 3: Transformation + Optimization ─────────────────────────────────────

class DbtRun(Base):
    __tablename__ = "dbt_runs"
    id = Column(String, primary_key=True)
    triggered_by = Column(String(255), nullable=True)
    models_generated = Column(Integer, default=0)
    models_succeeded = Column(Integer, default=0)
    models_failed = Column(Integer, default=0)
    tests_passed = Column(Integer, default=0)
    tests_failed = Column(Integer, default=0)
    mart_tables_created = Column(JSON, nullable=True)
    run_output = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class QueryOptimization(Base):
    __tablename__ = "query_optimizations"
    id = Column(String, primary_key=True)
    connection_id = Column(String, nullable=True)
    original_sql = Column(Text, nullable=False)
    optimized_sql = Column(Text, nullable=True)
    changes_made = Column(JSON, nullable=True)
    original_cost = Column(Float, nullable=True)
    optimized_cost = Column(Float, nullable=True)
    savings_percent = Column(Float, nullable=True)
    dollar_savings = Column(Float, nullable=True)
    execution_time_before_ms = Column(Integer, nullable=True)
    execution_time_after_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemMetric(Base):
    __tablename__ = "system_metrics"
    id = Column(String, primary_key=True)
    metric_name = Column(String(255), unique=True, nullable=False)
    metric_value = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ── Phase 4: Analytics + Insights ─────────────────────────────────────────────

class QueryHistory(Base):
    __tablename__ = "query_history"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=True)
    user_id = Column(String, nullable=True)
    question = Column(Text, nullable=False)
    generated_sql = Column(Text, nullable=True)
    optimized_sql = Column(Text, nullable=True)
    rows_returned = Column(Integer, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    chart_type = Column(String(50), nullable=True)
    feedback = Column(Integer, nullable=True)   # 1=thumbs_up, -1=thumbs_down
    created_at = Column(DateTime, default=datetime.utcnow)


class Insight(Base):
    __tablename__ = "insights"
    id = Column(String, primary_key=True)
    connection_id = Column(String, nullable=True)
    title = Column(String(120), nullable=False)
    insight = Column(Text, nullable=False)
    severity = Column(String(50), default="info")   # anomaly|warning|opportunity|info
    metric = Column(String(255), nullable=True)
    time_window = Column(String(10), nullable=True)  # 24h|7d|30d
    table_name = Column(String(255), nullable=True)
    supporting_sql = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=True)
    user_id = Column(String, nullable=True)
    title = Column(String(255), nullable=True)
    history = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ── Auth & Team ────────────────────────────────────────────────────────────────

class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(50), default="viewer")
    status = Column(String(50), default="active")
    invited_by = Column(String, nullable=True)
    invited_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, nullable=True)


class ApiToken(Base):
    __tablename__ = "api_tokens"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False)
    token_prefix = Column(String(20), nullable=False)
    scopes = Column(String(100), default="read")
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    revoked = Column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    actor = Column(String(255), nullable=False)
    action = Column(String(255), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(255), nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Pipeline SLA ───────────────────────────────────────────────────────────────

class PipelineSLA(Base):
    __tablename__ = "pipeline_sla"
    id = Column(String, primary_key=True)
    pipeline_name = Column(String(255), unique=True, nullable=False)
    sla_seconds = Column(Integer, nullable=False, default=3600)
    breach_mult = Column(Float, nullable=False, default=3.0)
    owner_email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── ETL Watermarks ─────────────────────────────────────────────────────────────

class EtlWatermark(Base):
    __tablename__ = "etl_watermarks"
    __table_args__ = (UniqueConstraint("pipeline_name", "table_name"),)
    id = Column(String, primary_key=True)
    pipeline_name = Column(String(255), nullable=False)
    table_name = Column(String(255), nullable=False)
    watermark_col = Column(String(255), nullable=False)
    watermark_val = Column(String(512), nullable=False)
    run_id = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Streaming Metrics ──────────────────────────────────────────────────────────

class StreamingMetric(Base):
    __tablename__ = "streaming_metrics"
    id = Column(String, primary_key=True)
    pipeline_name = Column(String(255), nullable=False)
    engine = Column(String(20), nullable=False)   # flink | spark | kafka
    run_id = Column(String(255), nullable=True)
    checkpoint_id = Column(String(255), nullable=True)
    checkpoint_status = Column(String(50), nullable=True)
    checkpoint_duration_ms = Column(Integer, nullable=True)
    backpressure_pct = Column(Float, nullable=True)
    micro_batch_ms = Column(Integer, nullable=True)
    records_per_second = Column(Float, nullable=True)
    consumer_lag = Column(Integer, nullable=True)
    watermark_lag_ms = Column(Integer, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)


# ── Healing ────────────────────────────────────────────────────────────────────

class SandboxTestRun(Base):
    __tablename__ = "sandbox_test_runs"
    id = Column(String, primary_key=True)
    incident_id = Column(String, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    fix_id = Column(String, ForeignKey("fixes.id", ondelete="CASCADE"), nullable=True)
    test_id = Column(String(10), nullable=False)
    test_name = Column(String(255), nullable=False)
    result = Column(String(10), nullable=False)   # PASS | FAIL | SKIP | ERROR
    duration_ms = Column(Integer, nullable=True)
    output = Column(Text, nullable=True)
    error_detail = Column(Text, nullable=True)
    ran_at = Column(DateTime, default=datetime.utcnow)


class HealingOutcome(Base):
    __tablename__ = "healing_outcomes"
    id = Column(String, primary_key=True)
    incident_id = Column(String, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    pipeline_name = Column(String(255), nullable=False)
    anomaly_type = Column(String(255), nullable=False)
    healing_strategy = Column(String(255), nullable=False)
    fix_code_hash = Column(String(64), nullable=True)
    outcome = Column(String(50), nullable=False)  # approved|rejected|auto_healed|expired
    mttr_seconds = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    approved_by = Column(String(255), nullable=True)
    detection_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FixLibrary(Base):
    __tablename__ = "fix_library"
    id = Column(String, primary_key=True)    # mirrors ChromaDB doc_id
    anomaly_type = Column(String(255), nullable=False)
    db_platform = Column(String(100), default="postgresql")
    fix_code = Column(Text, nullable=False)
    fix_language = Column(String(50), default="python")
    template_used = Column(String(255), nullable=True)
    root_cause = Column(Text, nullable=True)
    confidence_score = Column(Float, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    mttr_minutes = Column(Float, default=0)
    deprecated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Data Quality ───────────────────────────────────────────────────────────────

class QualityRule(Base):
    __tablename__ = "quality_rules"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    table_name = Column(String(255), nullable=False)
    column_name = Column(String(255), default="")
    rule_type = Column(String(50), nullable=False)
    condition = Column(Text, nullable=False)
    threshold = Column(Float, default=0)
    severity = Column(String(20), default="warning")
    enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    last_status = Column(String(20), default="pending")
    last_message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    results = relationship("QualityCheckResult", back_populates="rule")


class QualityCheckResult(Base):
    __tablename__ = "quality_check_results"
    id = Column(String, primary_key=True)
    rule_id = Column(String, ForeignKey("quality_rules.id", ondelete="CASCADE"), nullable=False)
    pipeline_run_id = Column(String, nullable=True)
    status = Column(String(20), nullable=False)  # pass|fail|error|skipped
    metric_value = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    message = Column(Text, nullable=True)
    row_count = Column(Integer, nullable=True)
    error_rows = Column(Integer, default=0)
    ran_at = Column(DateTime, default=datetime.utcnow)
    rule = relationship("QualityRule", back_populates="results")


class SchemaSnapshot(Base):
    __tablename__ = "schema_snapshots"
    id = Column(String, primary_key=True)
    table_name = Column(String(255), nullable=False)
    connection_id = Column(String, nullable=True)
    schema_json = Column(JSON, nullable=False)
    row_count = Column(Integer, default=0)
    snapshot_at = Column(DateTime, default=datetime.utcnow)


class DriftEvent(Base):
    __tablename__ = "drift_events"
    id = Column(String, primary_key=True)
    pipeline_name = Column(String(255), nullable=True)
    table_name = Column(String(255), nullable=False)
    event_type = Column(String(50), nullable=False)
    column_name = Column(String(255), default="")
    old_value = Column(Text, default="")
    new_value = Column(Text, default="")
    severity = Column(String(20), default="warning")
    incident_id = Column(String, ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)


class PiiScanResult(Base):
    __tablename__ = "pii_scan_results"
    id = Column(String, primary_key=True)
    table_name = Column(String(255), nullable=False)
    column_name = Column(String(255), nullable=False)
    pii_type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)
    detection_method = Column(String(20), default="regex")
    confidence = Column(Float, default=1.0)
    suppressed = Column(Boolean, default=False)
    tagged_at = Column(DateTime, default=datetime.utcnow)
    suppressed_at = Column(DateTime, nullable=True)
    suppressed_by = Column(String(255), default="")


# ── Lineage ────────────────────────────────────────────────────────────────────

class LineageNode(Base):
    __tablename__ = "lineage_nodes"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    node_type = Column(String(50), nullable=False)   # source|model|mart|sink|external|stream
    db_platform = Column(String(100), nullable=True)
    schema_name = Column(String(255), nullable=True)
    table_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    owner = Column(String(255), nullable=True)
    node_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    upstream_edges = relationship("LineageEdge", foreign_keys="LineageEdge.upstream_node_id", back_populates="upstream_node")
    downstream_edges = relationship("LineageEdge", foreign_keys="LineageEdge.downstream_node_id", back_populates="downstream_node")


class LineageEdge(Base):
    __tablename__ = "lineage_edges"
    __table_args__ = (UniqueConstraint("upstream_node_id", "downstream_node_id", "transform_type"),)
    id = Column(String, primary_key=True)
    upstream_node_id = Column(String, ForeignKey("lineage_nodes.id", ondelete="CASCADE"), nullable=False)
    downstream_node_id = Column(String, ForeignKey("lineage_nodes.id", ondelete="CASCADE"), nullable=False)
    transform_type = Column(String(50), default="etl")
    pipeline_name = Column(String(255), nullable=True)
    sql_expression = Column(Text, nullable=True)
    edge_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    upstream_node = relationship("LineageNode", foreign_keys=[upstream_node_id], back_populates="upstream_edges")
    downstream_node = relationship("LineageNode", foreign_keys=[downstream_node_id], back_populates="downstream_edges")


# ── Notifications & Alerts ─────────────────────────────────────────────────────

class NotificationConfig(Base):
    __tablename__ = "notification_config"
    id = Column(String, primary_key=True, default="default")
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    slack_webhook_url = Column(Text, default="")
    pagerduty_key = Column(Text, default="")
    email_from = Column(String(255), default="")
    email_smtp_host = Column(String(255), default="")
    email_smtp_port = Column(Integer, default=587)
    email_smtp_user = Column(String(255), default="")
    email_smtp_pass = Column(Text, default="")
    alert_rules = Column(JSON, default=list)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AlertRule(Base):
    __tablename__ = "alert_rules"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    condition = Column(String(100), nullable=False)
    channel = Column(String(50), nullable=False)
    threshold = Column(Float, default=0)
    cooldown_minutes = Column(Integer, default=60)
    enabled = Column(Boolean, default=True)
    last_fired_at = Column(DateTime, nullable=True)
    fire_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationHistory(Base):
    __tablename__ = "notification_history"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    rule_id = Column(String, ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True)
    channel = Column(String(50), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    status = Column(String(20), default="sent")
    error_message = Column(Text, default="")
    sent_at = Column(DateTime, default=datetime.utcnow)


# ── dbt Models ─────────────────────────────────────────────────────────────────

class DbtModel(Base):
    __tablename__ = "dbt_models"
    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("dbt_runs.id", ondelete="CASCADE"), nullable=False)
    model_name = Column(String(255), nullable=False)
    schema_name = Column(String(255), nullable=True)
    materialized = Column(String(50), default="table")
    status = Column(String(20), nullable=False)
    rows_affected = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error_detail = Column(Text, nullable=True)
    compiled_sql = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Reports ────────────────────────────────────────────────────────────────────

class Report(Base):
    __tablename__ = "reports"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    report_type = Column(String(50), nullable=False)
    config = Column(JSON, default=dict)
    schedule = Column(String(100), nullable=True)
    enabled = Column(Boolean, default=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    runs = relationship("ReportRun", back_populates="report")


class ReportRun(Base):
    __tablename__ = "report_runs"
    id = Column(String, primary_key=True)
    report_id = Column(String, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="running")
    output_url = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    triggered_by = Column(String(255), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    report = relationship("Report", back_populates="runs")
