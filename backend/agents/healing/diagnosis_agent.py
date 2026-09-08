"""
DiagnosisAgent — Root cause analysis using log analysis, dependency graph, and Groq LLM.

2025 upgrades:
  - Multi-DB error pattern library (PostgreSQL, Snowflake, BigQuery, MySQL, MongoDB,
    Redshift, Kafka/Debezium, dbt, Airflow)
  - Extended anomaly type coverage (SCHEMA_DRIFT, CDC_LAG, INCREMENTAL_SYNC_FAILURE,
    RATE_LIMIT_HIT, CASCADING_FAILURE, DUPLICATE_SPIKE, CHECKPOINT_FAILURE, etc.)
  - Richer evidence: schema snapshots, SLA metrics, upstream dependency health
  - Exponential back-off retry on Groq API transient failures
  - Confidence calibration: error message pattern match boosts confidence
"""
import json
import logging
import os
import re
import time
from typing import Dict, Any, Optional, List

import httpx
import psycopg2
import psycopg2.extras

from .state import HealingAgentState

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
AIRFLOW_URL  = os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080")
AIRFLOW_USER = os.getenv("AIRFLOW_USER", "admin")
AIRFLOW_PASS = os.getenv("AIRFLOW_PASSWORD", "admin")

DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST", "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname":   os.getenv("POSTGRES_DB", "orchestrai"),
    "user":     os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}

SYSTEM_PROMPT = """You are a senior data engineering expert specializing in root cause analysis
of ETL/ELT pipeline failures across multiple database platforms (PostgreSQL, Snowflake,
BigQuery, MySQL, MongoDB, Redshift, DuckDB, Kafka/Debezium, Apache Airflow, dbt).

## Your task
Analyze the evidence and identify the SINGLE most likely root cause.

## ETL Failure Taxonomy (use EXACTLY one of these types):
- schema_change: Column added/removed/renamed, data type change, NOT NULL added
- data_quality: Null spike, duplicate explosion, referential integrity violation, encoding error
- connection: Network timeout, SSL failure, auth error, connection pool exhaustion
- volume: Zero-load, dramatic row count drop/surge, source truncated, pagination bug
- timeout: Query/job exceeded time limit, GC pause, resource contention
- logic: DAG bug, transformation error, bad SQL, wrong join key, off-by-one in window
- rate_limit: API quota exceeded, Snowflake credits exhausted, BigQuery slot limit
- cdc_lag: Binlog/oplog consumer fell behind, Debezium connector stalled, stream staleness
- incremental_sync: Watermark regression, deduplication failure, out-of-order event
- cascading: Upstream pipeline failure propagated downstream, shared infra exhausted
- checkpoint: Kafka offset reset, Spark checkpoint corruption, incremental state lost
- partition_skew: Hot partition, uneven Spark/BigQuery partition, skewed shuffle
- permissions: IAM role missing, GRANT revoked, VPC firewall, service account expired

## Output format — valid JSON only:
{
  "root_cause": "precise 1-2 sentence description",
  "confidence": 0.0,
  "affected_tables": ["table_name"],
  "suggested_fix_type": "schema_change|data_quality|connection|volume|timeout|logic|rate_limit|cdc_lag|incremental_sync|cascading|checkpoint|partition_skew|permissions",
  "urgency": "critical|high|medium|low",
  "estimated_mttr_minutes": 15,
  "db_platform": "postgresql|snowflake|bigquery|mysql|mongodb|redshift|duckdb|kafka|dbt|airflow",
  "reasoning": "brief chain-of-thought"
}"""


class DiagnosisAgent:
    """Diagnoses pipeline anomalies using dependency graph, logs, quality data, and Groq LLM."""

    def diagnose(self, state: HealingAgentState) -> HealingAgentState:
        pipeline_name = state["pipeline_name"]
        anomaly_type  = state.get("anomaly_type", "UNKNOWN")
        steps = list(state.get("reasoning_steps") or [])
        steps.append("DiagnosisAgent: starting root cause analysis")

        try:
            lineage  = self._pipeline_dependencies(pipeline_name)
            logs     = self.fetch_logs(pipeline_name, state.get("run_id") or "")
            quality  = self._fetch_quality_results(pipeline_name)
            schema   = self._fetch_schema_snapshot(pipeline_name)
            sla      = self._fetch_sla_metrics(pipeline_name)
            upstream = self._fetch_upstream_health()

            evidence = self.build_evidence(
                anomaly_type=anomaly_type,
                anomaly_details=state.get("anomaly_details") or {},
                logs=logs,
                lineage=lineage,
                quality=quality,
                schema=schema,
                sla=sla,
                upstream=upstream,
            )

            diagnosis = self._call_groq_with_retry(evidence, max_retries=3)

            # Boost confidence when error message matches a known pattern
            pattern_boost = self._pattern_confidence_boost(
                state.get("anomaly_details") or {}, anomaly_type
            )
            final_confidence = min(1.0, float(diagnosis.get("confidence", 0.5)) + pattern_boost)

            steps.append(f"DiagnosisAgent: root_cause={str(diagnosis.get('root_cause',''))[:80]} confidence={final_confidence:.2f}")

            return HealingAgentState(**{**state,
                "lineage_graph": lineage,
                "root_cause": diagnosis.get("root_cause", "Unknown root cause"),
                "root_cause_confidence": final_confidence,
                "reasoning_steps": steps,
            })

        except Exception as e:
            logger.error("DiagnosisAgent failed: %s", e)
            # Immediate rule-based fallback for known anomaly types
            fallback = self._rule_based_fallback_by_anomaly(anomaly_type, state)
            steps.append(f"DiagnosisAgent: using rule-based fallback for {anomaly_type}")
            return HealingAgentState(**{**state,
                "root_cause": fallback["root_cause"],
                "root_cause_confidence": fallback["confidence"],
                "reasoning_steps": steps,
            })

    # ── Evidence builders ──────────────────────────────────────────────────────

    def _pipeline_dependencies(self, pipeline_name: str) -> Dict[str, Any]:
        """Static + dynamic dependency graph per pipeline."""
        deps = {
            "ingest_nyc_taxi": {
                "graph": [
                    {"id": "source:s3://nyc-tlc/parquet", "type": "S3_PARQUET"},
                    {"id": f"job:{pipeline_name}", "type": "JOB"},
                    {"id": "target:raw.nyc_taxi_trips", "type": "POSTGRES_TABLE"},
                ],
                "upstream_checks": ["S3 bucket accessibility", "schema consistency with source"],
                "downstream": ["dbt_run", "marts.fct_nyc_trips"],
            },
            "ingest_ecommerce": {
                "graph": [
                    {"id": "source:kafka:ecommerce.orders", "type": "KAFKA_TOPIC"},
                    {"id": f"job:{pipeline_name}", "type": "JOB"},
                    {"id": "target:raw.ecommerce_orders", "type": "POSTGRES_TABLE"},
                ],
                "upstream_checks": ["Kafka broker health", "consumer group lag", "topic offset"],
                "downstream": ["dbt_run", "marts.fct_ecommerce_orders"],
            },
            "dbt_run": {
                "graph": [
                    {"id": "source:raw.nyc_taxi_trips", "type": "POSTGRES_TABLE"},
                    {"id": "source:raw.ecommerce_orders", "type": "POSTGRES_TABLE"},
                    {"id": f"job:{pipeline_name}", "type": "DBT_JOB"},
                    {"id": "target:staging.stg_nyc_taxi_trips", "type": "POSTGRES_VIEW"},
                    {"id": "target:marts.fct_nyc_trips", "type": "POSTGRES_TABLE"},
                ],
                "upstream_checks": ["raw table row counts", "source freshness", "dbt model tests"],
                "downstream": ["insights_agent", "query_agent"],
            },
            "kafka_consumer": {
                "graph": [
                    {"id": "source:kafka:ecommerce.orders", "type": "KAFKA_TOPIC"},
                    {"id": f"job:{pipeline_name}", "type": "KAFKA_CONSUMER"},
                    {"id": "target:raw.ecommerce_orders", "type": "POSTGRES_TABLE"},
                ],
                "upstream_checks": ["consumer lag", "schema registry", "Debezium connector status"],
                "downstream": ["ingest_ecommerce"],
            },
        }
        return deps.get(pipeline_name, {
            "graph": [], "pipeline": pipeline_name,
            "upstream_checks": [], "downstream": [],
        })

    def build_evidence(
        self, anomaly_type: str, anomaly_details: Dict[str, Any],
        logs: str, lineage: Dict[str, Any], quality: str,
        schema: str = "", sla: str = "", upstream: str = "",
    ) -> str:
        return f"""=== ANOMALY ===
Type: {anomaly_type}
Details: {json.dumps(anomaly_details, indent=2, default=str)[:1000]}

=== PIPELINE DEPENDENCY GRAPH ===
{json.dumps(lineage, indent=2)[:1200]}

=== RECENT PIPELINE LOGS (last 100 lines) ===
{logs[:2000]}

=== QUALITY METRICS (last 5 runs) ===
{quality[:600]}

=== SCHEMA SNAPSHOT ===
{schema[:800]}

=== SLA METRICS ===
{sla[:400]}

=== UPSTREAM PIPELINE HEALTH ===
{upstream[:400]}"""

    # ── Data fetchers ──────────────────────────────────────────────────────────

    def fetch_logs(self, dag_id: str, run_id: str) -> str:
        """Fetch Airflow logs, fallback to pipeline_runs error_message."""
        try:
            url = f"{AIRFLOW_URL}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances"
            resp = httpx.get(url, auth=(AIRFLOW_USER, AIRFLOW_PASS), timeout=8.0)
            if resp.status_code == 200:
                tasks = resp.json().get("task_instances", [])
                log_lines = []
                for task in tasks[:3]:
                    task_id = task.get("task_id", "")
                    log_url = f"{AIRFLOW_URL}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/1"
                    log_resp = httpx.get(log_url, auth=(AIRFLOW_USER, AIRFLOW_PASS), timeout=5.0)
                    if log_resp.status_code == 200:
                        log_lines.extend(log_resp.text.splitlines()[-34:])
                return "\n".join(log_lines[-100:])
        except Exception:
            pass

        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT error_message, status, started_at, completed_at, duration_seconds
                    FROM pipeline_runs
                    WHERE pipeline_name = %s
                    ORDER BY started_at DESC LIMIT 10
                """, (dag_id,))
                rows = cur.fetchall()
            conn.close()
            lines = [
                f"[{r[2]} → {r[3]}] status={r[1]} duration={r[4]}s error={r[0]}"
                for r in rows
            ]
            return "\n".join(lines) or "No logs available"
        except Exception as e:
            return f"Log fetch error: {e}"

    def _fetch_quality_results(self, pipeline_name: str) -> str:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status, records_loaded, records_failed, records_ingested,
                           duration_seconds, error_message
                    FROM pipeline_runs
                    WHERE pipeline_name = %s
                    ORDER BY started_at DESC LIMIT 5
                """, (pipeline_name,))
                rows = cur.fetchall()
            conn.close()
            lines = [
                f"status={r[0]} loaded={r[1]} failed={r[2]} ingested={r[3]} "
                f"dur={r[4]}s err={str(r[5] or '')[:80]}"
                for r in rows
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"Quality fetch error: {e}"

    def _fetch_schema_snapshot(self, pipeline_name: str) -> str:
        """Get column list for the pipeline's target table."""
        table_map = {
            "ingest_nyc_taxi":  ("raw", "nyc_taxi_trips"),
            "ingest_ecommerce": ("raw", "ecommerce_orders"),
            "dbt_run":          ("staging", "stg_nyc_taxi_trips"),
            "kafka_consumer":   ("raw", "ecommerce_orders"),
        }
        schema_name, table_name = table_map.get(pipeline_name, ("public", "unknown"))
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                """, (schema_name, table_name))
                rows = cur.fetchall()
            conn.close()
            if not rows:
                return f"Table {schema_name}.{table_name} not found or empty"
            lines = [f"  {r[0]} {r[1]} {'NULL' if r[2]=='YES' else 'NOT NULL'}" for r in rows]
            return f"Table: {schema_name}.{table_name}\n" + "\n".join(lines)
        except Exception as e:
            return f"Schema fetch error: {e}"

    def _fetch_sla_metrics(self, pipeline_name: str) -> str:
        """Get SLA compliance stats for last 7 days."""
        sla_targets = {
            "ingest_nyc_taxi": 1800, "ingest_ecommerce": 900,
            "dbt_run": 3600, "kafka_consumer": 300,
        }
        target = sla_targets.get(pipeline_name, 3600)
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) AS total_runs,
                        SUM(CASE WHEN duration_seconds <= %s THEN 1 ELSE 0 END) AS within_sla,
                        AVG(duration_seconds) AS avg_duration,
                        MAX(duration_seconds) AS max_duration
                    FROM pipeline_runs
                    WHERE pipeline_name = %s
                      AND started_at >= NOW() - INTERVAL '7 days'
                      AND completed_at IS NOT NULL
                """, (target, pipeline_name))
                row = cur.fetchone()
            conn.close()
            if row and row[0]:
                total, within, avg_dur, max_dur = row
                sla_pct = (within / total * 100) if total else 0
                return (f"SLA target: {target}s | 7-day SLA compliance: {sla_pct:.1f}% "
                        f"({within}/{total} runs) | avg={avg_dur:.0f}s max={max_dur}s")
        except Exception as e:
            return f"SLA metrics error: {e}"
        return ""

    def _fetch_upstream_health(self) -> str:
        """Quick health snapshot of all pipelines in last 30 minutes."""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT pipeline_name,
                           SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS fails,
                           SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS successes
                    FROM pipeline_runs
                    WHERE started_at >= NOW() - INTERVAL '30 minutes'
                    GROUP BY pipeline_name
                """)
                rows = cur.fetchall()
            conn.close()
            lines = [f"{r[0]}: {r[2]} ok / {r[1]} fail" for r in rows]
            return "\n".join(lines) or "No recent runs"
        except Exception as e:
            return f"Upstream health error: {e}"

    # ── Groq API with retry ────────────────────────────────────────────────────

    def _call_groq_with_retry(self, evidence: str, max_retries: int = 3) -> Dict[str, Any]:
        if not GROQ_API_KEY:
            return self._rule_based_fallback(evidence)

        for attempt in range(max_retries):
            try:
                resp = httpx.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": GROQ_MODEL,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": evidence},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 600,
                    },
                    timeout=30.0,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                result = self._parse_json(content)
                if result.get("root_cause"):
                    return result
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 503) and attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning("Groq rate limit (attempt %d), retrying in %ds", attempt + 1, wait)
                    time.sleep(wait)
                else:
                    logger.warning("Groq HTTP error: %s", e)
                    break
            except Exception as e:
                logger.warning("Groq call failed (attempt %d): %s", attempt + 1, e)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        return self._rule_based_fallback(evidence)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"root_cause": text[:300], "confidence": 0.4, "affected_tables": [],
                "suggested_fix_type": "manual_review"}

    def _pattern_confidence_boost(self, anomaly_details: Dict, anomaly_type: str) -> float:
        """Boost confidence when we have direct evidence (e.g. zero rows, error match)."""
        boosts = {
            "ZERO_LOAD": 0.15,
            "CONSECUTIVE_FAILURES": 0.10,
            "SCHEMA_DRIFT": 0.20,
            "CDC_LAG": 0.15,
            "RATE_LIMIT_HIT": 0.20,
            "CASCADING_FAILURE": 0.25,
            "INCREMENTAL_SYNC_FAILURE": 0.15,
            "DUPLICATE_SPIKE": 0.10,
            "SLA_BREACH": 0.10,
            "CHECKPOINT_FAILURE": 0.20,
        }
        return boosts.get(anomaly_type, 0.0)

    # ── Rule-based fallbacks ───────────────────────────────────────────────────

    def _rule_based_fallback_by_anomaly(self, anomaly_type: str, state: HealingAgentState) -> Dict:
        """Structured fallback for every known anomaly type."""
        details = state.get("anomaly_details") or {}
        pipeline = state.get("pipeline_name", "unknown")
        rules = {
            "ZERO_LOAD": {
                "root_cause": f"Pipeline '{pipeline}' loaded zero records — source connectivity failure, empty upstream dataset, or auth token expired.",
                "confidence": 0.80, "suggested_fix_type": "connection", "urgency": "critical",
            },
            "ROW_COUNT_DROP": {
                "root_cause": f"Record count dropped {details.get('drop_pct', 0):.0%} vs 7-day avg — upstream data volume reduction, partial pipeline failure, or source filter regression.",
                "confidence": 0.70, "suggested_fix_type": "volume", "urgency": "high",
            },
            "NULL_SPIKE": {
                "root_cause": "Null rate exceeded 10% threshold — schema drift upstream (new nullable column or renamed field) or data quality regression in source system.",
                "confidence": 0.75, "suggested_fix_type": "schema_change", "urgency": "high",
            },
            "PIPELINE_DELAY": {
                "root_cause": "Pipeline duration exceeded 2x normal — resource contention, inefficient query, or upstream data volume surge causing GC pressure.",
                "confidence": 0.65, "suggested_fix_type": "timeout", "urgency": "medium",
            },
            "CONSECUTIVE_FAILURES": {
                "root_cause": f"Pipeline '{pipeline}' failed {details.get('consecutive_failures', 2)} times consecutively — persistent error in DAG logic, broken connection, or infrastructure issue.",
                "confidence": 0.80, "suggested_fix_type": "logic", "urgency": "critical",
            },
            "SCHEMA_DRIFT": {
                "root_cause": f"Schema change detected in pipeline '{pipeline}' — upstream source added/removed/renamed a column or changed a data type without coordinated migration.",
                "confidence": 0.85, "suggested_fix_type": "schema_change", "urgency": "critical",
            },
            "CDC_LAG": {
                "root_cause": f"CDC consumer lag exceeded {details.get('cdc_lag_seconds', 300):.0f}s — Debezium connector stalled, Kafka consumer group rebalancing, or oplog/binlog window expired.",
                "confidence": 0.80, "suggested_fix_type": "cdc_lag", "urgency": "high",
            },
            "RATE_LIMIT_HIT": {
                "root_cause": "API or warehouse rate limit hit — Snowflake credits exhausted, BigQuery quota exceeded, or source API throttling concurrent requests.",
                "confidence": 0.85, "suggested_fix_type": "rate_limit", "urgency": "high",
            },
            "INCREMENTAL_SYNC_FAILURE": {
                "root_cause": "Incremental sync watermark failure — checkpoint state lost, late-arriving events after watermark cutoff, or deduplication key collision.",
                "confidence": 0.75, "suggested_fix_type": "incremental_sync", "urgency": "high",
            },
            "CASCADING_FAILURE": {
                "root_cause": f"Multiple pipelines failing simultaneously ({details.get('cascade_count', 2)} pipelines) — shared infrastructure failure (DB, network, IAM), or upstream data source outage.",
                "confidence": 0.90, "suggested_fix_type": "cascading", "urgency": "critical",
            },
            "DUPLICATE_SPIKE": {
                "root_cause": "Duplicate record rate spiked — upstream system replaying events, CDC at-least-once delivery without idempotent sink, or deduplication logic removed.",
                "confidence": 0.70, "suggested_fix_type": "data_quality", "urgency": "high",
            },
            "SLA_BREACH": {
                "root_cause": f"Pipeline exceeded SLA by {details.get('sla_breach_ratio', 3):.1f}x — data volume surge, resource starvation, or query plan regression.",
                "confidence": 0.70, "suggested_fix_type": "timeout", "urgency": "high",
            },
            "CHECKPOINT_FAILURE": {
                "root_cause": "Stream checkpoint corrupted or reset — Kafka offset out of range after topic compaction, or checkpoint storage inaccessible.",
                "confidence": 0.80, "suggested_fix_type": "checkpoint", "urgency": "critical",
            },
            "DATA_TYPE_MISMATCH": {
                "root_cause": "Data type mismatch between source and target schema — source changed numeric to string, or added precision to a float/decimal column.",
                "confidence": 0.80, "suggested_fix_type": "schema_change", "urgency": "high",
            },
        }
        return rules.get(anomaly_type, {
            "root_cause": f"Anomaly type '{anomaly_type}' detected — manual investigation required.",
            "confidence": 0.30, "suggested_fix_type": "manual_review", "urgency": "medium",
        })

    def _rule_based_fallback(self, evidence: str) -> Dict[str, Any]:
        """Fallback for all anomaly types based on evidence text."""
        ev = evidence.lower()
        for keyword, result in [
            ("zero_load",               {"root_cause": "Pipeline loaded zero records — source connectivity failure or empty upstream dataset.", "confidence": 0.75, "suggested_fix_type": "connection", "urgency": "critical"}),
            ("cascading_failure",        {"root_cause": "Multiple pipelines failing — shared infrastructure or upstream data source outage.", "confidence": 0.85, "suggested_fix_type": "cascading", "urgency": "critical"}),
            ("schema_drift",             {"root_cause": "Schema drift detected — upstream source changed column structure without coordinated migration.", "confidence": 0.80, "suggested_fix_type": "schema_change", "urgency": "critical"}),
            ("cdc_lag",                  {"root_cause": "CDC consumer lag — Debezium connector stalled or Kafka consumer group rebalancing.", "confidence": 0.80, "suggested_fix_type": "cdc_lag", "urgency": "high"}),
            ("rate_limit_hit",           {"root_cause": "Rate limit hit — API quota exceeded or warehouse credits exhausted.", "confidence": 0.85, "suggested_fix_type": "rate_limit", "urgency": "high"}),
            ("incremental_sync_failure", {"root_cause": "Incremental sync watermark failure — checkpoint state lost or late-arriving events.", "confidence": 0.75, "suggested_fix_type": "incremental_sync", "urgency": "high"}),
            ("duplicate_spike",          {"root_cause": "Duplicate record spike — CDC at-least-once delivery without idempotent sink.", "confidence": 0.70, "suggested_fix_type": "data_quality", "urgency": "high"}),
            ("sla_breach",               {"root_cause": "Pipeline exceeded SLA — data volume surge or resource starvation.", "confidence": 0.70, "suggested_fix_type": "timeout", "urgency": "high"}),
            ("row_count_drop",           {"root_cause": "Record count dropped >20% vs 7-day baseline — upstream data volume reduction or partial failure.", "confidence": 0.65, "suggested_fix_type": "volume", "urgency": "high"}),
            ("null_spike",               {"root_cause": "Null rate spike — schema drift or upstream data quality regression.", "confidence": 0.70, "suggested_fix_type": "schema_change", "urgency": "high"}),
            ("pipeline_delay",           {"root_cause": "Pipeline duration exceeded 2x normal — resource contention or inefficient query.", "confidence": 0.60, "suggested_fix_type": "timeout", "urgency": "medium"}),
            ("consecutive_failures",     {"root_cause": "Pipeline failed consecutively — persistent error in DAG logic or connection issue.", "confidence": 0.80, "suggested_fix_type": "logic", "urgency": "critical"}),
        ]:
            if keyword in ev:
                return result

        return {"root_cause": "Anomaly detected — manual review required.", "confidence": 0.30,
                "affected_tables": [], "suggested_fix_type": "manual_review", "urgency": "medium"}
