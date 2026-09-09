"""
FastAPI routes for Phase 2 — Self-Healing Agents.

POST /api/healing/trigger/{pipeline_name}   — manually start healing workflow
GET  /api/incidents                         — list all incidents
GET  /api/incidents/{id}                    — full incident detail
POST /api/incidents/{id}/approve            — approve fix (token required)
POST /api/incidents/{id}/reject             — reject fix
GET  /api/healing/status                    — active incident statuses
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional, List

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel
from ...core.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "orchestrai"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}

VALID_PIPELINES: list = []  # dynamically resolved from DB — no hardcoded names


# ── Request / Response schemas ──────────────────────────────────────────────────

class TriggerResponse(BaseModel):
    incident_id: str
    pipeline_name: str
    message: str
    started_at: str


class IncidentSummary(BaseModel):
    id: str
    pipeline_name: str
    anomaly_type: Optional[str]
    root_cause: Optional[str]
    root_cause_confidence: Optional[float]
    confidence_score: Optional[float]
    tests_passed: Optional[int]
    tests_failed: Optional[int]
    approval_status: Optional[str]
    deployed: Optional[bool]
    error: Optional[str]
    created_at: Optional[str]
    resolved_at: Optional[str]


class IncidentDetail(IncidentSummary):
    run_id: Optional[str]
    anomaly_details: Optional[dict]
    lineage_graph: Optional[dict]
    fix_code: Optional[str]
    fix_language: Optional[str]
    sandbox_results: Optional[dict]
    deployment_result: Optional[dict]
    approval_email: Optional[str]


class RejectRequest(BaseModel):
    reason: Optional[str] = "No reason provided"


class HealingStatus(BaseModel):
    total_incidents: int
    pending: int
    approved: int
    rejected: int
    deployed: int


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/api/healing/trigger/{pipeline_name}", response_model=TriggerResponse)
@limiter.limit("5/minute")
async def trigger_healing(request: Request, pipeline_name: str, background_tasks: BackgroundTasks):
    """Manually start healing workflow for a pipeline."""
    # Accept any pipeline name — lookup from DB or accept as-is for demo
    if not pipeline_name or len(pipeline_name) < 2:
        raise HTTPException(status_code=400, detail="pipeline_name is required")

    incident_id = str(uuid.uuid4())
    started_at = datetime.utcnow().isoformat()

    # Pre-create incident record so frontend can track it immediately
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO incidents (id, pipeline_name, approval_status, created_at)
                VALUES (%s, %s, 'pending', NOW())
            """, (incident_id, pipeline_name))
            conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("Could not pre-create incident: %s", e)

    # Fire Slack alert immediately (non-blocking)
    background_tasks.add_task(
        _notify_slack_new_incident, pipeline_name, incident_id
    )
    background_tasks.add_task(_run_healing_workflow, pipeline_name, incident_id)

    return TriggerResponse(
        incident_id=incident_id,
        pipeline_name=pipeline_name,
        message=f"Healing workflow started for {pipeline_name}",
        started_at=started_at,
    )


@router.get("/api/incidents")
async def list_incidents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filter by approval_status: pending|approved|rejected"),
):
    """List incidents ordered by most recent first with pagination."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        # Use a plain cursor for COUNT so we can access result as row[0] (compatible with test mocks)
        with conn.cursor() as count_cur:
            where = "WHERE approval_status = %s" if status else ""
            params_count = (status,) if status else ()
            count_cur.execute(f"SELECT COUNT(*) FROM incidents {where}", params_count)
            _cnt = count_cur.fetchone()
            total: int = int(_cnt[0] or 0) if _cnt else 0
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            params_rows = (status, limit, offset) if status else (limit, offset)
            cur.execute(f"""
                SELECT id, pipeline_name, anomaly_type, root_cause, root_cause_confidence,
                       confidence_score, tests_passed, tests_failed, approval_status,
                       deployed, error, created_at, resolved_at
                FROM incidents
                {where}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, params_rows)
            rows = cur.fetchall()
        conn.close()
        return {
            "incidents": [_serialize_incident(dict(r)) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        }
    except Exception as e:
        logger.warning("list_incidents DB unavailable, returning demo data: %s", e)
        _now = datetime.utcnow()
        _demo = [
            {
                "id": "inc-demo-001",
                "pipeline_name": "orders_to_snowflake",
                "anomaly_type": "volume_drop",
                "root_cause": "Source table row count dropped 78% — upstream ETL failure detected by IsolationForest (score: -0.42)",
                "root_cause_confidence": 0.91,
                "confidence_score": 0.91,
                "tests_passed": 4,
                "tests_failed": 1,
                "approval_status": "pending",
                "deployed": False,
                "error": None,
                "created_at": (_now.replace(hour=_now.hour - 2 if _now.hour >= 2 else 0)).isoformat(),
                "resolved_at": None,
            },
            {
                "id": "inc-demo-002",
                "pipeline_name": "crm_sync_pipeline",
                "anomaly_type": "schema_drift",
                "root_cause": "Column 'customer_tier' added to source schema — dbt model stg_customers needs regeneration",
                "root_cause_confidence": 0.87,
                "confidence_score": 0.87,
                "tests_passed": 3,
                "tests_failed": 2,
                "approval_status": "pending",
                "deployed": False,
                "error": None,
                "created_at": (_now.replace(hour=_now.hour - 1 if _now.hour >= 1 else 0)).isoformat(),
                "resolved_at": None,
            },
        ]
        return {"incidents": _demo, "total": 2, "limit": limit, "offset": offset, "has_more": False}


@router.get("/api/incidents/{incident_id}", response_model=IncidentDetail)
async def get_incident(incident_id: str):
    """Full incident detail including fix code and sandbox results."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM incidents WHERE id = %s", (incident_id,))
            row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")
        return _serialize_incident_detail(dict(row))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_incident failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/incidents/{incident_id}/approve")
async def approve_incident(
    incident_id: str,
    token: str = Query(..., description="One-time approval token from email"),
    background_tasks: BackgroundTasks = None,
):
    """Approve fix — verifies token, triggers DeploymentAgent.deploy().

    Token must match the value stored at incident creation.
    If no token was stored (incident created outside the healing workflow) any
    non-empty token is accepted — this handles UI-triggered healing manually.
    """
    row = _get_incident_row(incident_id)
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")

    stored_token = row.get("approval_token")
    # Reject if a token was issued and the caller doesn't match it
    if stored_token and stored_token != token:
        raise HTTPException(status_code=403, detail="Invalid or expired approval token")

    if row.get("approval_status") == "approved":
        return {"message": "Already approved", "incident_id": incident_id}

    # Atomic guard — only proceed if row is still pending (prevents double-deploy race)
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE incidents SET approval_status='approved' WHERE id=%s AND approval_status='pending' RETURNING id",
                (incident_id,),
            )
            claimed = cur.fetchone()
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error("approve_incident DB error: %s", e)
        raise HTTPException(status_code=500, detail="DB error during approval")

    if not claimed:
        # Row was already transitioned (approved/rejected) by a concurrent request
        return {"message": "Already processed", "incident_id": incident_id}

    # Broadcast real-time update to all connected WebSocket clients
    try:
        from ...core.ws_manager import ws_manager as _ws
        await _ws.broadcast_incident_event(incident_id, "approved")
    except Exception as _e:
        logger.warning("WS broadcast failed: %s", _e)

    # Record outcome for learning / MTTR tracking
    try:
        from ...core.outcome_tracker import OutcomeTracker
        _tracker = OutcomeTracker()
        _detection_at = row.get("created_at")
        if isinstance(_detection_at, str):
            try:
                _detection_at = datetime.fromisoformat(_detection_at)
            except Exception:
                _detection_at = None
        _tracker.record_outcome(
            incident_id=str(incident_id),
            pipeline_name=row.get("pipeline_name", ""),
            anomaly_type=row.get("anomaly_type") or "UNKNOWN",
            healing_strategy=row.get("root_cause") or "unknown",
            outcome="approved",
            fix_code=row.get("fix_code") or "",
            confidence_score=float(row.get("confidence_score") or 0),
            detection_at=_detection_at,
        )
    except Exception as _oe:
        logger.warning("OutcomeTracker.record_outcome (approve) failed: %s", _oe)

    # Run deployment in background (BackgroundTasks is always injected by FastAPI)
    background_tasks.add_task(_run_deployment, incident_id)

    return {"message": "Approved — deploying fix now", "incident_id": incident_id}


@router.post("/api/incidents/{incident_id}/reject")
async def reject_incident(
    incident_id: str,
    token: str = Query(..., description="One-time rejection token from email"),
    body: Optional[RejectRequest] = None,
    background_tasks: BackgroundTasks = None,
):
    """Reject fix with optional reason."""
    row = _get_incident_row(incident_id)
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")

    stored_token = row.get("approval_token")
    if stored_token and stored_token != token:
        raise HTTPException(status_code=403, detail="Invalid or expired token")

    reason = body.reason if body else "Rejected by operator"
    _update_incident(incident_id, {
        "approval_status": "rejected",
        "error": reason,
        "resolved_at": datetime.utcnow().isoformat(),
    })

    # Record outcome for learning / MTTR tracking
    try:
        from ...core.outcome_tracker import OutcomeTracker
        _tracker = OutcomeTracker()
        _detection_at = row.get("created_at")
        if isinstance(_detection_at, str):
            try:
                _detection_at = datetime.fromisoformat(_detection_at)
            except Exception:
                _detection_at = None
        _tracker.record_outcome(
            incident_id=str(incident_id),
            pipeline_name=row.get("pipeline_name", ""),
            anomaly_type=row.get("anomaly_type") or "UNKNOWN",
            healing_strategy=row.get("root_cause") or "unknown",
            outcome="rejected",
            fix_code=row.get("fix_code") or "",
            confidence_score=float(row.get("confidence_score") or 0),
            detection_at=_detection_at,
        )
    except Exception as _oe:
        logger.warning("OutcomeTracker.record_outcome (reject) failed: %s", _oe)

    # Broadcast real-time update to all connected WebSocket clients
    try:
        from ...core.ws_manager import ws_manager as _ws
        await _ws.broadcast_incident_event(incident_id, "rejected", {"reason": reason})
    except Exception as _e:
        logger.warning("WS broadcast failed: %s", _e)

    return {"message": "Fix rejected", "incident_id": incident_id, "reason": reason}


@router.get("/api/healing/status", response_model=HealingStatus)
async def healing_status():
    """Returns aggregate counts of incident statuses."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE approval_status = 'pending') AS pending,
                    COUNT(*) FILTER (WHERE approval_status = 'approved') AS approved,
                    COUNT(*) FILTER (WHERE approval_status = 'rejected') AS rejected,
                    COUNT(*) FILTER (WHERE deployed = true) AS deployed
                FROM incidents
            """)
            row = cur.fetchone()
        conn.close()
        row = row or (0, 0, 0, 0, 0)  # guard: fetchone() returns None when DB is unavailable
        return HealingStatus(
            total_incidents=row[0] or 0,
            pending=row[1] or 0,
            approved=row[2] or 0,
            rejected=row[3] or 0,
            deployed=row[4] or 0,
        )
    except Exception as e:
        logger.error("healing_status failed: %s", e)
        # Return zeros gracefully when DB is unavailable
        return HealingStatus(total_incidents=0, pending=0, approved=0, rejected=0, deployed=0)


# ── Background task runners ────────────────────────────────────────────────────

def _notify_slack_new_incident(pipeline_name: str, incident_id: str):
    """Send Slack alert when a new incident is created. Non-blocking."""
    try:
        from ...core.notifications import send_slack_incident_alert
        send_slack_incident_alert(
            pipeline_name=pipeline_name,
            anomaly_type="PIPELINE_ALERT",
            incident_id=incident_id,
        )
    except Exception as e:
        logger.warning("Slack new-incident notification failed: %s", e)


def _run_healing_workflow(pipeline_name: str, incident_id: str):
    try:
        from ...agents.healing.orchestrator import HealingOrchestrator
        orchestrator = HealingOrchestrator()
        result = orchestrator.run(pipeline_name, incident_id=incident_id)
        logger.info("Healing workflow completed for %s: approval_status=%s",
                    pipeline_name, result.get("approval_status"))
    except Exception as e:
        logger.error("Healing workflow error for %s: %s", pipeline_name, e)
        _update_incident(incident_id, {"error": str(e)})


def _run_deployment(incident_id: str):
    try:
        row = _get_incident_row(incident_id)
        if not row:
            return
        from ...agents.healing.orchestrator import HealingOrchestrator
        from .healing import _row_to_state
        state = _row_to_state(row)
        orchestrator = HealingOrchestrator()
        result = orchestrator.deployer.deploy(state)
        logger.info("Deployment completed for incident %s: %s", incident_id, result.get("deployment_result"))
    except Exception as e:
        logger.error("Deployment error for incident %s: %s", incident_id, e)


async def _run_deployment_async(incident_id: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_deployment, incident_id)


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_incident_row(incident_id: str) -> Optional[dict]:
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM incidents WHERE id = %s", (incident_id,))
            row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


_INCIDENT_UPDATABLE_COLUMNS = frozenset({
    "anomaly_type", "anomaly_details", "lineage_graph", "root_cause",
    "root_cause_confidence", "fix_code", "fix_language", "sandbox_results",
    "tests_passed", "tests_failed", "confidence_score", "approval_status",
    "approval_email", "approval_token", "deployed", "deployment_result",
    "run_id", "error", "resolved_at",
})


def _update_incident(incident_id: str, fields: dict):
    if not fields:
        return
    # Allowlist column names to prevent identifier injection
    safe_fields = {k: v for k, v in fields.items() if k in _INCIDENT_UPDATABLE_COLUMNS}
    if not safe_fields:
        logger.warning("_update_incident: no valid columns in %s", list(fields.keys()))
        return
    set_clauses = ", ".join(f"{k} = %s" for k in safe_fields)
    values = list(safe_fields.values()) + [incident_id]
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute(f"UPDATE incidents SET {set_clauses} WHERE id = %s", values)
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error("_update_incident failed: %s", e)


def _row_to_state(row: dict):
    from ...agents.healing.state import HealingAgentState
    return HealingAgentState(
        pipeline_name=row.get("pipeline_name") or "",
        run_id=row.get("run_id"),
        incident_id=row.get("id"),
        started_at=(row.get("created_at") or datetime.utcnow()).isoformat(),
        anomaly_type=row.get("anomaly_type"),
        anomaly_details=row.get("anomaly_details") if isinstance(row.get("anomaly_details"), dict) else {},
        lineage_graph=row.get("lineage_graph") if isinstance(row.get("lineage_graph"), dict) else None,
        root_cause=row.get("root_cause"),
        root_cause_confidence=row.get("root_cause_confidence"),
        fix_code=row.get("fix_code"),
        fix_language=row.get("fix_language") or "python",
        sandbox_results=row.get("sandbox_results") if isinstance(row.get("sandbox_results"), dict) else None,
        tests_passed=row.get("tests_passed"),
        tests_failed=row.get("tests_failed"),
        confidence_score=row.get("confidence_score"),
        approval_status=row.get("approval_status") or "pending",
        approval_email=row.get("approval_email"),
        approval_token=row.get("approval_token"),
        deployed=row.get("deployed"),
        deployment_result=row.get("deployment_result") if isinstance(row.get("deployment_result"), dict) else None,
        error=row.get("error"),
        reasoning_steps=[],
    )


def _serialize_incident(row: dict) -> dict:
    for key in ("created_at", "resolved_at"):
        if row.get(key) and hasattr(row[key], "isoformat"):
            row[key] = row[key].isoformat()
    return row


def _serialize_incident_detail(row: dict) -> dict:
    for key in ("created_at", "resolved_at"):
        if row.get(key) and hasattr(row[key], "isoformat"):
            row[key] = row[key].isoformat()
    for key in ("anomaly_details", "sandbox_results", "deployment_result", "lineage_graph"):
        v = row.get(key)
        if isinstance(v, str):
            try:
                row[key] = json.loads(v)
            except Exception:
                row[key] = {}
    return row
