"""
HealingOrchestrator — LangGraph StateGraph wiring all 5 agents.

Flow:
  START → monitoring → should_heal?
  → YES → diagnosis → fix_writer → sandbox → sandbox_passed?
  → YES → deployment (send email) → wait_approval → approved?
      → YES → deploy → learn → END
      → NO  → store_rejection → END
  → NO (no anomaly) → END
  → NO (sandbox failed) → END
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime

from langgraph.graph import END, StateGraph

from ...db.pool import pool_context
from .deployment_agent import DeploymentAgent
from .diagnosis_agent import DiagnosisAgent
from .fix_writer_agent import FixWriterAgent
from .monitoring_agent import MonitoringAgent
from .sandbox_agent import SandboxAgent
from .state import HealingAgentState

logger = logging.getLogger(__name__)

SANDBOX_CONFIDENCE_THRESHOLD = 0.75  # static fallback — overridden per-anomaly by LearningAgent


class HealingOrchestrator:
    """Autonomous self-healing pipeline orchestrated via LangGraph."""

    def __init__(self):
        self.monitor = MonitoringAgent()
        self.diagnoser = DiagnosisAgent()
        self.fix_writer = FixWriterAgent()
        self.sandbox = SandboxAgent()
        self.deployer = DeploymentAgent()
        self.graph = self._build_graph()

    # ── Graph Construction ─────────────────────────────────────────────────────

    def _build_graph(self):
        g = StateGraph(HealingAgentState)

        g.add_node("monitoring",       self._node_monitoring)
        g.add_node("diagnosis",        self._node_diagnosis)
        g.add_node("fix_writer",       self._node_fix_writer)
        g.add_node("sandbox",          self._node_sandbox)
        g.add_node("deployment",       self._node_deployment)
        g.add_node("wait_approval",    self._node_wait_approval)
        g.add_node("deploy",           self._node_deploy)
        g.add_node("learn",            self._node_learn)
        g.add_node("store_rejection",  self._node_store_rejection)

        g.set_entry_point("monitoring")

        # monitoring → conditional
        g.add_conditional_edges("monitoring", self._route_should_heal, {
            "heal": "diagnosis",
            "healthy": END,
        })
        g.add_edge("diagnosis", "fix_writer")
        g.add_edge("fix_writer", "sandbox")
        g.add_conditional_edges("sandbox", self._route_sandbox_passed, {
            "passed": "deployment",
            "failed": END,
        })
        g.add_edge("deployment", "wait_approval")
        g.add_conditional_edges("wait_approval", self._route_approved, {
            "approved": "deploy",
            "rejected": "store_rejection",
            "pending": END,
        })
        g.add_edge("deploy", "learn")
        g.add_edge("learn", END)
        g.add_edge("store_rejection", END)

        return g.compile()

    # ── Routing functions ──────────────────────────────────────────────────────

    def _route_should_heal(self, state: HealingAgentState) -> str:
        return "heal" if state.get("anomaly_type") else "healthy"

    def _route_sandbox_passed(self, state: HealingAgentState) -> str:
        score = state.get("confidence_score") or 0.0
        anomaly_type = state.get("anomaly_type") or ""
        threshold = self._learned_threshold(anomaly_type)
        logger.info(
            "_route_sandbox_passed: score=%.3f threshold=%.3f anomaly=%s",
            score, threshold, anomaly_type,
        )
        return "passed" if score >= threshold else "failed"

    def _learned_threshold(self, anomaly_type: str) -> float:
        """
        Fetch per-anomaly-type confidence threshold from LearningAgent.
        Falls back to SANDBOX_CONFIDENCE_THRESHOLD when fewer than 3 historical fixes exist.
        """
        try:
            from ..learning.learning_agent import LearningAgent
            return LearningAgent().learned_threshold_for_anomaly(anomaly_type, SANDBOX_CONFIDENCE_THRESHOLD)
        except Exception as e:
            logger.warning("Could not fetch learned threshold, using default: %s", e)
            return SANDBOX_CONFIDENCE_THRESHOLD

    def _route_approved(self, state: HealingAgentState) -> str:
        status = state.get("approval_status") or "pending"
        if status == "approved":
            return "approved"
        if status == "rejected":
            return "rejected"
        return "pending"

    # ── Node implementations ───────────────────────────────────────────────────

    def _node_monitoring(self, state: HealingAgentState) -> HealingAgentState:
        """Node 1: run rule-based + ML checks on the pipeline."""
        pipeline_name = state.get("pipeline_name") or ""
        self._log(state, f"MonitoringAgent checking: {pipeline_name}")
        anomaly_state = self.monitor.check_pipeline(pipeline_name)
        if anomaly_state:
            # Merge anomaly data into current state, preserve incident_id if set
            return HealingAgentState(**{**state,
                "anomaly_type": anomaly_state["anomaly_type"],
                "anomaly_details": anomaly_state["anomaly_details"],
                "run_id": anomaly_state.get("run_id") or state.get("run_id"),
                "reasoning_steps": (state.get("reasoning_steps") or []) + (anomaly_state.get("reasoning_steps") or []),
            })
        return state  # no anomaly → routing will send to END

    def _node_diagnosis(self, state: HealingAgentState) -> HealingAgentState:
        """Node 2: find root cause with Groq LLM + lineage + logs."""
        self._log(state, f"DiagnosisAgent analysing anomaly: {state.get('anomaly_type')}")
        new_state = self.diagnoser.diagnose(state)
        # Create incident record in DB
        incident_id = self._create_incident(new_state)
        # Notify on-call — anomaly detected
        self._notify(
            subject=f"🚨 Anomaly Detected — {new_state.get('pipeline_name', 'unknown')}",
            body=(
                f"Anomaly type: {new_state.get('anomaly_type', 'UNKNOWN')}\n"
                f"Root cause: {new_state.get('root_cause', 'Diagnosing…')}\n"
                f"Incident ID: {incident_id}"
            ),
            severity="warning",
        )
        return HealingAgentState(**{**new_state, "incident_id": incident_id})

    def _node_fix_writer(self, state: HealingAgentState) -> HealingAgentState:
        """Node 3: generate fix code via RAG cache or Groq LLM."""
        self._log(state, "FixWriterAgent: generating fix code")
        return self.fix_writer.write_fix(state)

    def _node_sandbox(self, state: HealingAgentState) -> HealingAgentState:
        """Node 4: run 12-point test suite in Docker."""
        self._log(state, "SandboxAgent: running 12-point test suite in Docker")
        new_state = self.sandbox.run(state)
        self._update_incident_sandbox(new_state)
        return new_state

    def _node_deployment(self, state: HealingAgentState) -> HealingAgentState:
        """Node 5a: send approval email, set approval_status=pending."""
        self._log(state, f"DeploymentAgent: sending approval email to {os.getenv('ALERT_EMAIL','')}")
        email_sent, token = self.deployer.send_approval_email(state)
        steps = list(state.get("reasoning_steps") or [])
        steps.append(f"DeploymentAgent: approval email {'sent' if email_sent else 'FAILED'}")
        return HealingAgentState(**{**state,
            "approval_status": "pending",
            "approval_email": os.getenv("ALERT_EMAIL", ""),
            "approval_token": token,
            "reasoning_steps": steps,
        })

    def _node_wait_approval(self, state: HealingAgentState) -> HealingAgentState:
        """Node 5b: check DB for approval status (set by API endpoint)."""
        incident_id = state.get("incident_id")
        if not incident_id:
            return state
        try:
            with pool_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT approval_status FROM incidents WHERE id = %s", (incident_id,))
                    row = cur.fetchone()
            if row and row[0]:
                return HealingAgentState(**{**state, "approval_status": str(row[0])})
        except Exception as e:
            logger.warning("wait_approval DB read failed: %s", e)
        return state

    def _node_deploy(self, state: HealingAgentState) -> HealingAgentState:
        """Node 5c: deploy approved fix to DAG folder + restart Airflow."""
        self._log(state, "DeploymentAgent: deploying approved fix")
        new_state = self.deployer.deploy(state)
        if new_state.get("deployed"):
            self._notify(
                subject=f"✅ Fix Deployed — {new_state.get('pipeline_name', 'unknown')}",
                body=(
                    f"Anomaly: {new_state.get('anomaly_type', 'UNKNOWN')}\n"
                    f"Fix confidence: {round((new_state.get('confidence_score') or 0) * 100)}%\n"
                    f"Incident ID: {new_state.get('incident_id')}\n"
                    f"Deployment: {new_state.get('deployment_result', 'completed')}"
                ),
                severity="success",
            )
        return new_state

    def _node_learn(self, state: HealingAgentState) -> HealingAgentState:
        """Node 6: store successful fix in ChromaDB for future reuse."""
        self._log(state, "Learning: storing fix in ChromaDB")
        if state.get("deployed") and state.get("fix_code"):
            try:
                from ..learning.learning_agent import LearningAgent
                learner = LearningAgent()
                learner.store_fix(incident_state=dict(state))
            except Exception as e:
                logger.warning("ChromaDB store failed: %s", e)
        steps = list(state.get("reasoning_steps") or [])
        steps.append("LearningAgent: fix stored in ChromaDB")
        return HealingAgentState(**{**state, "reasoning_steps": steps})

    def _node_store_rejection(self, state: HealingAgentState) -> HealingAgentState:
        """Store rejection in DB for audit trail."""
        incident_id = state.get("incident_id")
        if incident_id:
            try:
                with pool_context() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE incidents SET approval_status='rejected', resolved_at=NOW()
                            WHERE id = %s
                        """, (incident_id,))
                        conn.commit()
            except Exception as e:
                logger.warning("store_rejection DB update failed: %s", e)
        steps = list(state.get("reasoning_steps") or [])
        steps.append("Fix rejected by operator")
        return HealingAgentState(**{**state, "reasoning_steps": steps})

    # ── Public entry points ────────────────────────────────────────────────────

    def run(self, pipeline_name, incident_id: str | None = None) -> HealingAgentState:
        """Synchronous entry point — runs the full healing workflow.

        pipeline_name can be a string OR a dict with keys:
          pipeline_name, anomaly_type, anomaly_details (used by validation / test callers).
        """
        # Accept dict form: run({'pipeline_name': '...', 'anomaly_type': '...', ...})
        extra_overrides: dict = {}
        if isinstance(pipeline_name, dict):
            d = pipeline_name
            extra_overrides = {k: v for k, v in d.items() if k != 'pipeline_name'}
            pipeline_name = d.get('pipeline_name', '')

        initial = self._make_initial_state(pipeline_name, incident_id)
        # Apply any extra keys from dict form (e.g. anomaly_type, anomaly_details)
        for k, v in extra_overrides.items():
            if k in initial:
                initial[k] = v
        try:
            return self.graph.invoke(initial)
        except Exception as e:
            logger.error("HealingOrchestrator.run failed: %s", e)
            initial["error"] = str(e)
            return initial

    async def arun(self, pipeline_name: str, incident_id: str | None = None) -> HealingAgentState:
        """Async entry point."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run, pipeline_name, incident_id)

    def run_all_pipelines(self):
        """Monitoring heartbeat: check all 4 pipelines, heal any anomalies."""
        anomalies = self.monitor.run_all_checks()
        results = []
        for state in anomalies:
            logger.info("Healing pipeline: %s (anomaly: %s)", state["pipeline_name"], state["anomaly_type"])
            result = self.run(state["pipeline_name"])
            results.append(result)
        return results

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _make_initial_state(self, pipeline_name: str, incident_id: str | None) -> HealingAgentState:
        return HealingAgentState(
            pipeline_name=pipeline_name,
            run_id=None,
            incident_id=incident_id,
            started_at=datetime.utcnow().isoformat(),
            anomaly_type=None,
            anomaly_details=None,
            lineage_graph=None,
            root_cause=None,
            root_cause_confidence=None,
            fix_code=None,
            fix_language=None,
            sandbox_results=None,
            tests_passed=None,
            tests_failed=None,
            confidence_score=None,
            approval_status="pending",
            approval_email=None,
            approval_token=None,
            deployed=None,
            deployment_result=None,
            error=None,
            reasoning_steps=[],
        )

    def _create_incident(self, state: HealingAgentState) -> str:
        import json as _json
        incident_id = state.get("incident_id") or str(uuid.uuid4())
        try:
            with pool_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO incidents (
                            id, pipeline_name, run_id, anomaly_type, anomaly_details,
                            root_cause, root_cause_confidence, approval_status, created_at
                        ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, 'pending', NOW())
                        ON CONFLICT (id) DO UPDATE
                            SET root_cause = EXCLUDED.root_cause,
                                root_cause_confidence = EXCLUDED.root_cause_confidence
                    """, (
                        incident_id,
                        state.get("pipeline_name", ""),
                        state.get("run_id", ""),
                        state.get("anomaly_type", ""),
                        _json.dumps(state.get("anomaly_details") or {}, default=str),
                        state.get("root_cause", ""),
                        state.get("root_cause_confidence") or 0.0,
                    ))
                    conn.commit()
        except Exception as e:
            logger.error("_create_incident failed: %s", e)
        return incident_id

    def _update_incident_sandbox(self, state: HealingAgentState):
        import json as _json
        incident_id = state.get("incident_id")
        if not incident_id:
            return
        try:
            with pool_context() as conn, conn.cursor() as cur:
                cur.execute("""
                        UPDATE incidents SET
                            fix_code = %s, fix_language = %s,
                            sandbox_results = %s::jsonb,
                            tests_passed = %s, tests_failed = %s,
                            confidence_score = %s
                        WHERE id = %s
                    """, (
                    state.get("fix_code", ""),
                    state.get("fix_language", "python"),
                    _json.dumps(state.get("sandbox_results") or {}),
                    state.get("tests_passed") or 0,
                    state.get("tests_failed") or 0,
                    state.get("confidence_score") or 0.0,
                    incident_id,
                ))
                conn.commit()
        except Exception as e:
            logger.warning("_update_incident_sandbox failed: %s", e)

    def _notify(self, subject: str, body: str, severity: str = "info"):
        """
        Best-effort notification dispatch — never blocks the healing pipeline.

        Channel routing:
          - All events  → Slack (if SLACK_WEBHOOK_URL or notification_config.slack_webhook_url set)
          - critical / warning events → PagerDuty (if PAGERDUTY_KEY or notification_config.pagerduty_key set)
        """
        channels = ["slack"]
        if severity in ("critical", "warning"):
            channels.append("pagerduty")

        try:
            import httpx as _httpx
            api_base = os.getenv("INTERNAL_API_URL", "http://localhost:8000")
            _httpx.post(
                f"{api_base}/api/notifications/dispatch",
                json={"subject": subject, "body": body, "severity": severity, "channels": channels},
                timeout=5,
                headers={"X-Dev-Mode": "true"},
            )
        except Exception as e:
            # Fallback: call Slack + PagerDuty directly if API is unavailable
            self._direct_notify(subject, body, severity, channels, error=str(e))

    def _direct_notify(self, subject: str, body: str, severity: str, channels: list, error: str = ""):
        """Direct webhook dispatch — used when the notifications API is unreachable."""
        import httpx as _httpx

        if "slack" in channels:
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            if slack_url:
                try:
                    color_map = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#3b82f6", "success": "#22c55e"}
                    _httpx.post(slack_url, json={
                        "attachments": [{
                            "color": color_map.get(severity, "#3b82f6"),
                            "title": f"🤖 OrchestrAI — {subject}",
                            "text": body,
                            "footer": "OrchestrAI Alerts",
                        }]
                    }, timeout=5)
                except Exception as se:
                    logger.warning("Direct Slack dispatch failed: %s", se)
            else:
                logger.warning("Notification dispatch skipped (API error: %s, no SLACK_WEBHOOK_URL)", error)

        if "pagerduty" in channels:
            pd_key = os.getenv("PAGERDUTY_KEY", "")
            if pd_key:
                try:
                    _httpx.post("https://events.pagerduty.com/v2/enqueue", json={
                        "routing_key": pd_key,
                        "event_action": "trigger",
                        "payload": {
                            "summary": f"OrchestrAI: {subject}",
                            "severity": "critical" if severity == "critical" else "warning",
                            "source": "OrchestrAI",
                            "custom_details": {"message": body},
                        }
                    }, timeout=5)
                except Exception as pe:
                    logger.warning("Direct PagerDuty dispatch failed: %s", pe)

    def _log(self, state: HealingAgentState, msg: str):
        ts = datetime.utcnow().strftime("%H:%M:%S")
        logger.info("[OrchestrAI %s] %s", ts, msg)
        steps = state.get("reasoning_steps")
        if steps is not None:
            steps.append(f"[{ts}] {msg}")
