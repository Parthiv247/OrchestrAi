"""
DiagnosisAgent — Finds root cause using log analysis, a pipeline dependency map, and Groq LLM.

Steps: load dependencies → read logs → read quality results → build evidence → ask Groq.
"""
import json
import logging
import os
import re
from typing import Dict, Any, Optional

import httpx
import psycopg2
import psycopg2.extras

from .state import HealingAgentState

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
AIRFLOW_URL = os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080")
AIRFLOW_USER = os.getenv("AIRFLOW_USER", "admin")
AIRFLOW_PASS = os.getenv("AIRFLOW_PASSWORD", "admin")

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "orchestrai"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}

SYSTEM_PROMPT = """You are a data engineering expert specializing in root cause analysis of ETL pipeline failures.

Analyze the evidence provided and identify the SINGLE most likely root cause.
Be precise and specific — avoid vague answers.

Return ONLY valid JSON in exactly this format:
{
  "root_cause": "string — precise 1-2 sentence description of root cause",
  "confidence": 0.0,
  "affected_tables": ["table_name"],
  "suggested_fix_type": "schema_change|data_quality|connection|logic|volume|timeout",
  "urgency": "critical|high|medium|low",
  "reasoning": "string — brief chain-of-thought"
}"""


class DiagnosisAgent:
    """Diagnoses pipeline anomalies using a dependency map, logs, quality results, and Groq LLM."""

    def diagnose(self, state: HealingAgentState) -> HealingAgentState:
        """Main entry point — returns updated state with root_cause populated."""
        pipeline_name = state["pipeline_name"]
        steps = list(state.get("reasoning_steps") or [])
        steps.append("DiagnosisAgent: starting root cause analysis")

        try:
            lineage = self._pipeline_dependencies(pipeline_name)
            logs = self.fetch_logs(pipeline_name, state.get("run_id") or "")
            quality = self._fetch_quality_results(pipeline_name)

            evidence = self.build_evidence(
                anomaly_type=state.get("anomaly_type", "UNKNOWN"),
                anomaly_details=state.get("anomaly_details") or {},
                logs=logs,
                lineage=lineage,
                quality=quality,
            )

            diagnosis = self._call_groq(evidence)
            steps.append(f"DiagnosisAgent: root_cause={diagnosis.get('root_cause', '')[:80]}")

            return HealingAgentState(
                **{**state,
                   "lineage_graph": lineage,
                   "root_cause": diagnosis.get("root_cause", "Unknown root cause"),
                   "root_cause_confidence": float(diagnosis.get("confidence", 0.5)),
                   "reasoning_steps": steps,
                   }
            )
        except Exception as e:
            logger.error("DiagnosisAgent failed: %s", e)
            steps.append(f"DiagnosisAgent error: {e}")
            return HealingAgentState(**{**state, "root_cause": f"Diagnosis failed: {e}", "root_cause_confidence": 0.1, "reasoning_steps": steps})

    def _pipeline_dependencies(self, pipeline_name: str) -> Dict[str, Any]:
        """Static map of each pipeline's upstream/downstream datasets (no external service)."""
        deps = {
            "ingest_nyc_taxi": {
                "graph": [
                    {"id": "dataset:orchestrai:s3://nyc-tlc/parquet", "type": "DATASET"},
                    {"id": f"job:orchestrai:{pipeline_name}", "type": "JOB"},
                    {"id": "dataset:orchestrai:raw.nyc_taxi_trips", "type": "DATASET"},
                ]
            },
            "ingest_ecommerce": {
                "graph": [
                    {"id": "dataset:orchestrai:kafka:ecommerce.orders", "type": "DATASET"},
                    {"id": f"job:orchestrai:{pipeline_name}", "type": "JOB"},
                    {"id": "dataset:orchestrai:raw.ecommerce_orders", "type": "DATASET"},
                ]
            },
            "dbt_run": {
                "graph": [
                    {"id": "dataset:orchestrai:raw.nyc_taxi_trips", "type": "DATASET"},
                    {"id": "dataset:orchestrai:raw.ecommerce_orders", "type": "DATASET"},
                    {"id": f"job:orchestrai:{pipeline_name}", "type": "JOB"},
                    {"id": "dataset:orchestrai:staging.stg_nyc_taxi_trips", "type": "DATASET"},
                ]
            },
            "kafka_consumer": {
                "graph": [
                    {"id": "dataset:orchestrai:kafka:ecommerce.orders", "type": "DATASET"},
                    {"id": f"job:orchestrai:{pipeline_name}", "type": "JOB"},
                    {"id": "dataset:orchestrai:raw.ecommerce_orders", "type": "DATASET"},
                ]
            },
        }
        return deps.get(pipeline_name, {"graph": [], "pipeline": pipeline_name})

    def fetch_logs(self, dag_id: str, run_id: str) -> str:
        """Fetch last 100 lines of Airflow task logs for the failed run."""
        try:
            url = f"{AIRFLOW_URL}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances"
            resp = httpx.get(url, auth=(AIRFLOW_USER, AIRFLOW_PASS), timeout=10.0)
            if resp.status_code == 200:
                tasks = resp.json().get("task_instances", [])
                log_lines = []
                for task in tasks[:3]:
                    task_id = task.get("task_id", "")
                    log_url = f"{AIRFLOW_URL}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/1"
                    log_resp = httpx.get(log_url, auth=(AIRFLOW_USER, AIRFLOW_PASS), timeout=5.0)
                    if log_resp.status_code == 200:
                        lines = log_resp.text.splitlines()[-34:]
                        log_lines.extend(lines)
                return "\n".join(log_lines[-100:])
        except Exception:
            pass

        # Fallback: pull error_message from pipeline_runs table
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT error_message, status, started_at, completed_at
                    FROM pipeline_runs
                    WHERE pipeline_name = %s
                    ORDER BY started_at DESC
                    LIMIT 5
                """, (dag_id,))
                rows = cur.fetchall()
            conn.close()
            lines = []
            for row in rows:
                lines.append(f"[{row[2]}→{row[3]}] status={row[1]} error={row[0]}")
            return "\n".join(lines) or "No logs available"
        except Exception as e:
            return f"Log fetch error: {e}"

    def build_evidence(
        self,
        anomaly_type: str,
        anomaly_details: Dict[str, Any],
        logs: str,
        lineage: Dict[str, Any],
        quality: str,
    ) -> str:
        return f"""=== ANOMALY ===
Type: {anomaly_type}
Details: {json.dumps(anomaly_details, indent=2, default=str)}

=== PIPELINE DEPENDENCIES ===
{json.dumps(lineage, indent=2)[:1500]}

=== RECENT PIPELINE LOGS ===
{logs[:2000]}

=== QUALITY CHECK RESULTS ===
{quality[:500]}"""

    def _fetch_quality_results(self, pipeline_name: str) -> str:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status, records_loaded, records_failed, error_message
                    FROM pipeline_runs
                    WHERE pipeline_name = %s
                    ORDER BY started_at DESC
                    LIMIT 3
                """, (pipeline_name,))
                rows = cur.fetchall()
            conn.close()
            lines = [f"status={r[0]} loaded={r[1]} failed={r[2]} err={r[3]}" for r in rows]
            return "\n".join(lines)
        except Exception as e:
            return f"Quality fetch error: {e}"

    def _call_groq(self, evidence: str) -> Dict[str, Any]:
        """Call Groq API directly via httpx (no LangChain dependency here)."""
        if not GROQ_API_KEY:
            return self._rule_based_fallback(evidence)
        try:
            payload = {
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": evidence},
                ],
                "temperature": 0.1,
                "max_tokens": 512,
            }
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=30.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return self._parse_json(content)
        except Exception as e:
            logger.warning("Groq call failed, using rule-based fallback: %s", e)
            return self._rule_based_fallback(evidence)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"root_cause": text[:300], "confidence": 0.4, "affected_tables": [], "suggested_fix_type": "manual_review"}

    def _rule_based_fallback(self, evidence: str) -> Dict[str, Any]:
        ev_lower = evidence.lower()
        if "zero_load" in ev_lower:
            return {"root_cause": "Pipeline loaded zero records — likely source connectivity failure or empty upstream dataset.", "confidence": 0.75, "affected_tables": [], "suggested_fix_type": "connection"}
        if "row_count_drop" in ev_lower:
            return {"root_cause": "Record count dropped >20% vs 7-day baseline — upstream data volume reduction or partial pipeline failure.", "confidence": 0.65, "affected_tables": [], "suggested_fix_type": "volume"}
        if "null_spike" in ev_lower:
            return {"root_cause": "Null rate spiked beyond 10% threshold — schema drift or upstream data quality regression.", "confidence": 0.70, "affected_tables": [], "suggested_fix_type": "schema_change"}
        if "pipeline_delay" in ev_lower:
            return {"root_cause": "Pipeline duration exceeded 2x normal — resource contention or inefficient query.", "confidence": 0.60, "affected_tables": [], "suggested_fix_type": "timeout"}
        if "consecutive_failures" in ev_lower:
            return {"root_cause": "Pipeline failed consecutively — persistent error in DAG logic or connection issue.", "confidence": 0.80, "affected_tables": [], "suggested_fix_type": "logic"}
        return {"root_cause": "Anomaly detected but root cause unclear — manual review required.", "confidence": 0.30, "affected_tables": [], "suggested_fix_type": "manual_review"}
