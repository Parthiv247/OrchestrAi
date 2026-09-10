"""Shared state TypedDict used by all 5 healing agents in the LangGraph StateGraph."""
from typing import Any, TypedDict


class HealingAgentState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────────────
    pipeline_name: str
    run_id: str | None
    incident_id: str | None
    started_at: str

    # ── Monitoring ────────────────────────────────────────────────────────────
    anomaly_type: str | None          # e.g. "ROW_COUNT_DROP", "NULL_SPIKE", "ZERO_LOAD"
    anomaly_details: dict[str, Any] | None  # raw metrics dict from monitoring agent

    # ── Lineage / evidence ────────────────────────────────────────────────────
    lineage_graph: dict[str, Any] | None    # static pipeline dependency map

    # ── Diagnosis ─────────────────────────────────────────────────────────────
    root_cause: str | None            # plain-English root cause from Groq
    root_cause_confidence: float | None  # 0.0–1.0

    # ── Fix ───────────────────────────────────────────────────────────────────
    fix_code: str | None              # Python or SQL fix code
    fix_language: str | None         # "python" | "sql"

    # ── Sandbox ───────────────────────────────────────────────────────────────
    sandbox_results: dict[str, Any] | None  # dict of test_name → pass/fail
    tests_passed: int | None
    tests_failed: int | None
    confidence_score: float | None   # tests_passed / 12

    # ── Approval ──────────────────────────────────────────────────────────────
    approval_status: str | None      # "pending" | "approved" | "rejected"
    approval_email: str | None       # email address the approval request was sent to
    approval_token: str | None       # one-time UUID token stored in DB

    # ── Deployment ────────────────────────────────────────────────────────────
    deployed: bool | None
    deployment_result: dict[str, Any] | None

    # ── Meta ──────────────────────────────────────────────────────────────────
    error: str | None
    reasoning_steps: list[str]          # audit trail of agent decisions
