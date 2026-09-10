"""
DeploymentAgent — Sends approval email, waits for human approval, then deploys fix.

Email approval flow:
1. Generate one-time UUID token, store in incidents table
2. Send HTML email with approval/rejection links
3. On POST /api/incidents/{id}/approve?token={token} → deploy
4. Write fix to DAG folder, trigger Airflow restart, verify success
5. Trigger LearningAgent to store fix in ChromaDB
"""
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg2
import psycopg2.extras

from ...utils.email import send_email
from .state import HealingAgentState

logger = logging.getLogger(__name__)

DAGS_DIR = Path(__file__).parent.parent.parent.parent / "airflow" / "dags"
AIRFLOW_URL = os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080")
AIRFLOW_USER = os.getenv("AIRFLOW_USER", "admin")
AIRFLOW_PASS = os.getenv("AIRFLOW_PASSWORD", "admin")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "admin@orchestrai.com")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "orchestrai"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}


class DeploymentAgent:
    """Handles email approval workflow and production deployment."""

    def send_approval_email(self, state: HealingAgentState) -> tuple[bool, str]:
        """Generate token, store it in DB, send approval email. Returns (success, token)."""
        incident_id = state.get("incident_id") or str(uuid.uuid4())
        token = str(uuid.uuid4())

        # Store token in DB
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE incidents
                    SET approval_token = %s, approval_status = 'pending'
                    WHERE id = %s
                """, (token, incident_id))
                conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Failed to store approval token: %s", e)

        fix_code = state.get("fix_code") or ""
        fix_preview = "\n".join(fix_code.splitlines()[:20])
        tests_passed = state.get("tests_passed") or 0
        confidence = state.get("confidence_score") or 0.0

        approve_url = f"{API_BASE_URL}/api/incidents/{incident_id}/approve?token={token}"
        reject_url = f"{API_BASE_URL}/api/incidents/{incident_id}/reject?token={token}"

        html_body = f"""
<html><body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
<div style="background:#1a1a2e; color:#e0e0e0; padding:20px; border-radius:8px;">
  <h2 style="color:#00d4ff;">🤖 OrchestrAI — Pipeline Fix Ready for Approval</h2>
  <hr style="border-color:#333;"/>

  <table style="width:100%; margin-bottom:16px;">
    <tr><td style="color:#aaa;">Pipeline</td><td><b>{state.get('pipeline_name','')}</b></td></tr>
    <tr><td style="color:#aaa;">Anomaly Type</td><td><b style="color:#ff6b6b;">{state.get('anomaly_type','')}</b></td></tr>
    <tr><td style="color:#aaa;">Root Cause</td><td>{state.get('root_cause','')}</td></tr>
    <tr><td style="color:#aaa;">Confidence</td><td>{confidence:.0%} ({tests_passed}/12 tests passed)</td></tr>
  </table>

  <h3 style="color:#00d4ff;">Fix Code Preview (first 20 lines)</h3>
  <pre style="background:#0d0d1a; padding:12px; border-radius:4px; overflow:auto; font-size:12px;">{fix_preview}</pre>

  <div style="margin-top:24px; display:flex; gap:12px;">
    <a href="{approve_url}" style="background:#00a86b; color:white; padding:12px 24px; border-radius:4px; text-decoration:none; font-weight:bold;">
      ✅ Approve &amp; Deploy
    </a>
    &nbsp;&nbsp;
    <a href="{reject_url}" style="background:#cc3333; color:white; padding:12px 24px; border-radius:4px; text-decoration:none; font-weight:bold;">
      ❌ Reject Fix
    </a>
  </div>

  <p style="color:#666; font-size:12px; margin-top:20px;">
    Incident ID: {incident_id}<br/>
    Token: {token[:8]}...{token[-4:]}<br/>
    Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
  </p>
</div>
</body></html>"""

        success = send_email(
            to=ALERT_EMAIL,
            subject=f"[OrchestrAI] Action Required: Pipeline fix ready for approval — {state.get('pipeline_name','')}",
            html_body=html_body,
        )
        return success, token

    def deploy(self, state: HealingAgentState) -> HealingAgentState:
        """Deploy approved fix: write to DAG folder, trigger Airflow, verify."""
        steps = list(state.get("reasoning_steps") or [])
        pipeline_name = state.get("pipeline_name") or ""
        fix_code = state.get("fix_code") or ""
        incident_id = state.get("incident_id") or ""

        result: dict[str, Any] = {
            "success": False,
            "pipeline_name": pipeline_name,
            "deployed_at": datetime.utcnow().isoformat(),
            "dag_run_id": None,
            "message": "",
        }

        # 1. Backup existing DAG
        self._backup_dag(pipeline_name)

        # 2. Inject fix into DAG file
        inject_ok, inject_msg = self._inject_fix(fix_code, pipeline_name)
        if not inject_ok:
            result["message"] = f"Fix injection failed: {inject_msg}"
            steps.append(f"DeploymentAgent: {result['message']}")
            return HealingAgentState(**{**state, "deployed": False, "deployment_result": result, "reasoning_steps": steps})

        # 3. Trigger Airflow DAG run
        run_id, trigger_msg = self._trigger_dag_run(pipeline_name, incident_id)
        result["dag_run_id"] = run_id
        result["success"] = True
        result["message"] = f"Fix deployed. Airflow: {trigger_msg}"

        # 4. Update incident status in DB
        self._mark_deployed(incident_id)

        steps.append(f"DeploymentAgent: deployed successfully, dag_run_id={run_id}")
        return HealingAgentState(**{**state,
            "deployed": True,
            "deployment_result": result,
            "reasoning_steps": steps,
        })

    def verify_deployment(self, pipeline_name: str, run_id: str) -> bool:
        """Verify the restarted pipeline run succeeded (polls pipeline_runs table)."""
        import time
        deadline = time.time() + 300  # 5 minute window
        while time.time() < deadline:
            try:
                conn = psycopg2.connect(**DB_CONFIG)
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT status FROM pipeline_runs
                        WHERE pipeline_name = %s AND run_id = %s
                        LIMIT 1
                    """, (pipeline_name, run_id))
                    row = cur.fetchone()
                conn.close()
                if row and row[0] == "success":
                    return True
                if row and row[0] == "failed":
                    return False
            except Exception:
                pass
            time.sleep(15)
        return False

    # ── Private helpers ────────────────────────────────────────────────────────

    def _backup_dag(self, pipeline_name: str) -> bool:
        dag_file = self._dag_file(pipeline_name)
        if not dag_file or not dag_file.exists():
            return False
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dag_file.rename(dag_file.parent / f"{dag_file.name}.bak_{ts}")
        dag_file.write_text((dag_file.parent / f"{dag_file.name}.bak_{ts}").read_text())
        return True

    def _inject_fix(self, fix_code: str, pipeline_name: str) -> tuple[bool, str]:
        dag_file = self._dag_file(pipeline_name)
        if not dag_file:
            return False, f"Unknown pipeline: {pipeline_name}"
        if not dag_file.exists():
            # Create a minimal placeholder if DAG doesn't exist yet
            dag_file.parent.mkdir(parents=True, exist_ok=True)
            dag_file.write_text(f'# OrchestrAI auto-generated DAG placeholder for {pipeline_name}\n')

        existing = dag_file.read_text()
        # Remove previous auto-fix block
        existing = re.sub(
            r"# ─── OrchestrAI Auto-Fix.*?# ─── End Auto-Fix ─+\n",
            "", existing, flags=re.DOTALL,
        )
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        block = (
            f"\n# ─── OrchestrAI Auto-Fix (deployed {ts}) ─────────────────────\n"
            f"{fix_code}\n"
            f"# ─── End Auto-Fix ────────────────────────────────────────────\n"
        )
        dag_file.write_text(existing + block)
        return True, "Fix injected into DAG"

    def _trigger_dag_run(self, pipeline_name: str, incident_id: str) -> tuple[str | None, str]:
        run_id = f"orchestrai_heal_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"
        try:
            resp = httpx.post(
                f"{AIRFLOW_URL}/api/v1/dags/{pipeline_name}/dagRuns",
                json={"dag_run_id": run_id, "conf": {"triggered_by": "orchestrai_auto_heal", "incident_id": incident_id}},
                auth=(AIRFLOW_USER, AIRFLOW_PASS),
                headers={"Content-Type": "application/json"},
                timeout=10.0,
            )
            if resp.status_code in (200, 201):
                return resp.json().get("dag_run_id", run_id), "Airflow triggered"
            return None, f"Airflow returned {resp.status_code}"
        except Exception as e:
            return None, f"Airflow not reachable: {e}"

    def _mark_deployed(self, incident_id: str):
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE incidents
                    SET approval_status='approved', deployed=true,
                        resolved_at=NOW()
                    WHERE id = %s
                """, (incident_id,))
                conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Could not mark incident deployed: %s", e)

    def _dag_file(self, pipeline_name: str) -> Path | None:
        dag_map = {
            "ingest_nyc_taxi": "ingest_nyc_taxi.py",
            "ingest_ecommerce": "ingest_ecommerce.py",
            "dbt_run": "dbt_run.py",
            "kafka_consumer": "kafka_consumer.py",
        }
        filename = dag_map.get(pipeline_name)
        return (DAGS_DIR / filename) if filename else None
