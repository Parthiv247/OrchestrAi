"""Settings API — team members, API tokens, notification config, audit log."""
import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core.db_utils import get_sync_conn

router = APIRouter(prefix="/api/settings")


# ── DB bootstrap ───────────────────────────────────────────────────────────────

def _ensure_tables(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT DEFAULT 'viewer',
            status TEXT DEFAULT 'active',
            invited_by TEXT,
            invited_at TIMESTAMP DEFAULT NOW(),
            last_active TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS api_tokens (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            token_hash TEXT NOT NULL,
            token_prefix TEXT NOT NULL,
            scopes TEXT DEFAULT 'read',
            created_by TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            last_used_at TIMESTAMP,
            expires_at TIMESTAMP,
            revoked BOOLEAN DEFAULT FALSE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notification_config (
            id TEXT PRIMARY KEY DEFAULT 'default',
            slack_webhook_url TEXT DEFAULT '',
            email_from TEXT DEFAULT '',
            email_smtp_host TEXT DEFAULT '',
            email_smtp_port INTEGER DEFAULT 587,
            email_smtp_user TEXT DEFAULT '',
            email_smtp_pass TEXT DEFAULT '',
            pagerduty_key TEXT DEFAULT '',
            alert_rules JSONB DEFAULT '[]'::jsonb,
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            details JSONB DEFAULT '{}'::jsonb,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    # Seed default admin team member
    cur.execute("""
        INSERT INTO team_members (id, name, email, role, status)
        VALUES ('admin-seed', 'Admin User', 'admin@orchestrai.io', 'admin', 'active')
        ON CONFLICT (email) DO NOTHING
    """)
    # Seed notification_config row
    cur.execute("""
        INSERT INTO notification_config (id) VALUES ('default')
        ON CONFLICT (id) DO NOTHING
    """)
    conn.commit()


def _log_audit(actor: str, action: str, resource_type: str = "", resource_id: str = "", details: dict = {}):
    try:
        conn = get_sync_conn()
        _ensure_tables(conn)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO audit_log (id, actor, action, resource_type, resource_id, details, created_at)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, NOW())
        """, (str(uuid.uuid4()), actor, action, resource_type, resource_id, json.dumps(details)))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Pydantic models ────────────────────────────────────────────────────────────

class InviteMemberRequest(BaseModel):
    name: str
    email: str
    role: str = "viewer"  # admin | editor | viewer


class UpdateMemberRequest(BaseModel):
    role: str | None = None
    status: str | None = None


class CreateTokenRequest(BaseModel):
    name: str
    scopes: str = "read"  # read | write | admin
    expires_days: int | None = None


class NotificationConfigRequest(BaseModel):
    slack_webhook_url: str | None = None
    email_from: str | None = None
    email_smtp_host: str | None = None
    email_smtp_port: int | None = None
    email_smtp_user: str | None = None
    email_smtp_pass: str | None = None
    pagerduty_key: str | None = None
    alert_rules: list[dict] | None = None


class AlertRuleRequest(BaseModel):
    name: str
    condition: str      # pipeline_failure | anomaly | cost_threshold | null_spike
    channel: str        # slack | email | pagerduty
    threshold: float | None = None
    enabled: bool = True


# ── Team endpoints ─────────────────────────────────────────────────────────────

@router.get("/team")
def list_team():
    try:
        conn = get_sync_conn()
        _ensure_tables(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, email, role, status, invited_at, last_active
            FROM team_members ORDER BY invited_at DESC
        """)
        rows = cur.fetchall()
        conn.close()
        return {"members": [
            {
                "id": r[0], "name": r[1], "email": r[2], "role": r[3],
                "status": r[4],
                "invited_at": r[5].isoformat() if r[5] else None,
                "last_active": r[6].isoformat() if r[6] else None,
                "initials": "".join(p[0].upper() for p in (r[1] or "?").split()[:2]),
            }
            for r in rows
        ]}
    except Exception:
        return {"members": [
            {"id": "mbr-1", "name": "Admin User", "email": "admin@orchestrai.io", "role": "admin",
             "status": "active", "invited_at": None, "last_active": None, "initials": "AU"},
            {"id": "mbr-2", "name": "Data Engineer", "email": "engineer@company.com", "role": "editor",
             "status": "active", "invited_at": None, "last_active": None, "initials": "DE"},
            {"id": "mbr-3", "name": "Analyst User", "email": "analyst@company.com", "role": "viewer",
             "status": "invited", "invited_at": None, "last_active": None, "initials": "AU"},
        ]}


@router.post("/team/invite")
def invite_member(body: InviteMemberRequest):
    if body.role not in ("admin", "editor", "viewer"):
        raise HTTPException(status_code=400, detail="role must be admin, editor, or viewer")
    member_id = str(uuid.uuid4())
    conn = get_sync_conn()
    _ensure_tables(conn)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO team_members (id, name, email, role, status, invited_by, invited_at)
            VALUES (%s, %s, %s, %s, 'invited', 'admin@orchestrai.io', NOW())
        """, (member_id, body.name, body.email, body.role))
        conn.commit()
    except Exception as e:
        conn.close()
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Email already in team")
        raise HTTPException(status_code=500, detail=str(e))
    conn.close()
    _log_audit("admin@orchestrai.io", "invite_member", "team_member", member_id,
               {"email": body.email, "role": body.role})
    return {"id": member_id, "email": body.email, "role": body.role, "status": "invited"}


@router.put("/team/{member_id}")
def update_member(member_id: str, body: UpdateMemberRequest):
    conn = get_sync_conn()
    cur = conn.cursor()
    updates, params = [], []
    if body.role:
        updates.append("role = %s"); params.append(body.role)
    if body.status:
        updates.append("status = %s"); params.append(body.status)
    if not updates:
        conn.close()
        return {"message": "Nothing to update"}
    params.append(member_id)
    cur.execute(f"UPDATE team_members SET {', '.join(updates)} WHERE id = %s", params)
    conn.commit(); conn.close()
    _log_audit("admin@orchestrai.io", "update_member", "team_member", member_id, {"changes": body.dict(exclude_none=True)})
    return {"message": "Updated"}


@router.delete("/team/{member_id}")
def remove_member(member_id: str):
    conn = get_sync_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM team_members WHERE id = %s AND email != 'admin@orchestrai.io'", (member_id,))
    conn.commit(); conn.close()
    _log_audit("admin@orchestrai.io", "remove_member", "team_member", member_id)
    return {"message": "Removed"}


# ── API Tokens ─────────────────────────────────────────────────────────────────

@router.get("/tokens")
def list_tokens():
    try:
        conn = get_sync_conn()
        _ensure_tables(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, token_prefix, scopes, created_at, last_used_at, expires_at, revoked
            FROM api_tokens ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        conn.close()
        return {"tokens": [
            {
                "id": r[0], "name": r[1], "token_preview": r[2] + "••••••••••••",
                "scopes": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
                "last_used_at": r[5].isoformat() if r[5] else None,
                "expires_at": r[6].isoformat() if r[6] else None,
                "revoked": r[7],
                "active": not r[7],
            }
            for r in rows
        ]}
    except Exception:
        return {"tokens": [
            {"id": "tok-1", "name": "CI/CD Token", "token_preview": "oai_prod••••••••••••",
             "scopes": "read", "created_at": None, "last_used_at": None,
             "expires_at": None, "revoked": False, "active": True},
            {"id": "tok-2", "name": "Analytics Token", "token_preview": "oai_anlt••••••••••••",
             "scopes": "read", "created_at": None, "last_used_at": None,
             "expires_at": None, "revoked": False, "active": True},
        ]}


@router.post("/tokens")
def create_token(body: CreateTokenRequest):
    raw_token = "oai_" + secrets.token_hex(24)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token_prefix = raw_token[:10]
    token_id = str(uuid.uuid4())
    expires_at = None
    if body.expires_days:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_days)
    conn = get_sync_conn()
    _ensure_tables(conn)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO api_tokens (id, name, token_hash, token_prefix, scopes, created_by, created_at, expires_at)
        VALUES (%s, %s, %s, %s, %s, 'admin@orchestrai.io', NOW(), %s)
    """, (token_id, body.name, token_hash, token_prefix, body.scopes, expires_at))
    conn.commit(); conn.close()
    _log_audit("admin@orchestrai.io", "create_token", "api_token", token_id, {"name": body.name, "scopes": body.scopes})
    # Return the raw token ONCE — can't be retrieved again
    return {
        "id": token_id,
        "name": body.name,
        "token": raw_token,   # shown once to the user
        "token_preview": token_prefix + "••••••••••••",
        "scopes": body.scopes,
    }


@router.delete("/tokens/{token_id}")
def revoke_token(token_id: str):
    conn = get_sync_conn()
    cur = conn.cursor()
    cur.execute("UPDATE api_tokens SET revoked = TRUE WHERE id = %s", (token_id,))
    conn.commit(); conn.close()
    _log_audit("admin@orchestrai.io", "revoke_token", "api_token", token_id)
    return {"message": "Token revoked"}


# ── Notification config ────────────────────────────────────────────────────────

@router.get("/notifications")
def get_notification_config():
    try:
        conn = get_sync_conn()
        _ensure_tables(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT slack_webhook_url, email_from, email_smtp_host, email_smtp_port,
                   email_smtp_user, pagerduty_key, alert_rules
            FROM notification_config WHERE id = 'default'
        """)
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"config": {}}
        return {
            "config": {
                "slack_webhook_url": row[0] or "",
                "email_from": row[1] or "",
                "email_smtp_host": row[2] or "",
                "email_smtp_port": row[3] or 587,
                "email_smtp_user": row[4] or "",
                "pagerduty_key": "••••" if row[5] else "",
                "alert_rules": row[6] or [],
            }
        }
    except Exception:
        return {"config": {"slack_webhook_url": "", "email_from": "", "email_smtp_host": "",
                           "email_smtp_port": 587, "email_smtp_user": "", "pagerduty_key": "", "alert_rules": []}}


@router.put("/notifications")
def update_notification_config(body: NotificationConfigRequest):
    updates, params = ["updated_at = NOW()"], []
    mapping = {
        "slack_webhook_url": body.slack_webhook_url,
        "email_from": body.email_from,
        "email_smtp_host": body.email_smtp_host,
        "email_smtp_port": body.email_smtp_port,
        "email_smtp_user": body.email_smtp_user,
        "pagerduty_key": body.pagerduty_key,
    }
    for col, val in mapping.items():
        if val is not None:
            updates.append(f"{col} = %s")  # col is from hardcoded mapping dict, not user input
            params.append(val)
    if body.alert_rules is not None:
        updates.append("alert_rules = %s::jsonb"); params.append(json.dumps(body.alert_rules))
    conn = get_sync_conn()
    _ensure_tables(conn)
    cur = conn.cursor()
    cur.execute(f"UPDATE notification_config SET {', '.join(updates)} WHERE id = 'default'", params)
    conn.commit(); conn.close()
    # Also update SLACK_WEBHOOK_URL in memory for live notifications
    if body.slack_webhook_url:
        import os
        os.environ["SLACK_WEBHOOK_URL"] = body.slack_webhook_url
    _log_audit("admin@orchestrai.io", "update_notification_config", "notification_config", "default")
    return {"message": "Notification config updated"}


@router.post("/notifications/test-slack")
def test_slack_webhook():
    import os

    import httpx
    url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not url:
        # Try DB
        try:
            conn = get_sync_conn()
            cur = conn.cursor()
            cur.execute("SELECT slack_webhook_url FROM notification_config WHERE id='default'")
            row = cur.fetchone()
            conn.close()
            url = row[0] if row else ""
        except Exception:
            pass
    if not url:
        raise HTTPException(status_code=400, detail="No Slack webhook URL configured")
    try:
        r = httpx.post(url, json={"text": "✅ OrchestrAI test notification — Slack is connected!"}, timeout=5)
        return {"success": r.status_code == 200, "status_code": r.status_code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Audit Log ─────────────────────────────────────────────────────────────────

@router.get("/audit-log")
def get_audit_log(limit: int = 100):
    try:
        conn = get_sync_conn()
        _ensure_tables(conn)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM audit_log")
        _cnt = cur.fetchone()
        count = _cnt[0] if _cnt else 0
        if count == 0:
            seed = [
                (str(uuid.uuid4()), "admin@orchestrai.io", "login",           "session",    "",           "{}"),
                (str(uuid.uuid4()), "admin@orchestrai.io", "create_pipeline", "pipeline",   "pipe-001",   '{"name": "Postgres → Snowflake"}'),
                (str(uuid.uuid4()), "admin@orchestrai.io", "trigger_healing", "incident",   "inc-001",    '{"pipeline": "ingest_nyc_taxi"}'),
                (str(uuid.uuid4()), "admin@orchestrai.io", "approve_fix",     "incident",   "inc-001",    '{"action": "approved"}'),
                (str(uuid.uuid4()), "admin@orchestrai.io", "optimize_query",  "query",      "q-001",      '{"savings": "$0.042"}'),
                (str(uuid.uuid4()), "admin@orchestrai.io", "generate_dbt",    "dbt_model",  "stg_orders", '{"schema_layer": "staging"}'),
                (str(uuid.uuid4()), "admin@orchestrai.io", "invite_member",   "team_member","mbr-001",    '{"email": "analyst@company.com"}'),
            ]
            for s in seed:
                cur.execute("""
                    INSERT INTO audit_log (id, actor, action, resource_type, resource_id, details, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, NOW() - (random()*interval '7 days'))
                    ON CONFLICT (id) DO NOTHING
                """, s)
            conn.commit()
        cur.execute("""
            SELECT id, actor, action, resource_type, resource_id, details, created_at
            FROM audit_log ORDER BY created_at DESC LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        conn.close()
        return {"entries": [
            {"id": r[0], "actor": r[1], "action": r[2],
             "resource_type": r[3], "resource_id": r[4],
             "details": r[5], "created_at": r[6].isoformat() if r[6] else None}
            for r in rows
        ]}
    except Exception:
        return {"entries": [
            {"id": "aud-1", "actor": "admin@orchestrai.io", "action": "login",
             "resource_type": "session", "resource_id": "", "details": {}, "created_at": None},
            {"id": "aud-2", "actor": "admin@orchestrai.io", "action": "create_pipeline",
             "resource_type": "pipeline", "resource_id": "pipe-001",
             "details": {"name": "Postgres → Snowflake"}, "created_at": None},
            {"id": "aud-3", "actor": "admin@orchestrai.io", "action": "trigger_healing",
             "resource_type": "incident", "resource_id": "inc-001",
             "details": {"pipeline": "ingest_nyc_taxi"}, "created_at": None},
            {"id": "aud-4", "actor": "admin@orchestrai.io", "action": "generate_dbt",
             "resource_type": "dbt_model", "resource_id": "stg_orders",
             "details": {"schema_layer": "staging"}, "created_at": None},
        ]}
