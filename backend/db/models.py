"""SQLAlchemy models for OrchestrAI."""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, Float, Text, JSON,
    DateTime, ForeignKey, Enum as SAEnum
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
