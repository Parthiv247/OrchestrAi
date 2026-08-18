"""Shared state TypedDict used by all 5 healing agents in the LangGraph StateGraph."""
from typing import TypedDict, Optional, List, Any, Dict


class HealingAgentState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────────────
    pipeline_name: str
    run_id: Optional[str]
    incident_id: Optional[str]
    started_at: str

    # ── Monitoring ────────────────────────────────────────────────────────────
    anomaly_type: Optional[str]          # e.g. "ROW_COUNT_DROP", "NULL_SPIKE", "ZERO_LOAD"
    anomaly_details: Optional[Dict[str, Any]]  # raw metrics dict from monitoring agent

    # ── Lineage / evidence ────────────────────────────────────────────────────
    lineage_graph: Optional[Dict[str, Any]]    # static pipeline dependency map

    # ── Diagnosis ─────────────────────────────────────────────────────────────
    root_cause: Optional[str]            # plain-English root cause from Groq
    root_cause_confidence: Optional[float]  # 0.0–1.0

    # ── Fix ───────────────────────────────────────────────────────────────────
    fix_code: Optional[str]              # Python or SQL fix code
    fix_language: Optional[str]         # "python" | "sql"

    # ── Sandbox ───────────────────────────────────────────────────────────────
    sandbox_results: Optional[Dict[str, Any]]  # dict of test_name → pass/fail
    tests_passed: Optional[int]
    tests_failed: Optional[int]
    confidence_score: Optional[float]   # tests_passed / 12

    # ── Approval ──────────────────────────────────────────────────────────────
    approval_status: Optional[str]      # "pending" | "approved" | "rejected"
    approval_email: Optional[str]       # email address the approval request was sent to
    approval_token: Optional[str]       # one-time UUID token stored in DB

    # ── Deployment ────────────────────────────────────────────────────────────
    deployed: Optional[bool]
    deployment_result: Optional[Dict[str, Any]]

    # ── Meta ──────────────────────────────────────────────────────────────────
    error: Optional[str]
    reasoning_steps: List[str]          # audit trail of agent decisions
