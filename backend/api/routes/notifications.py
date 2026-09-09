"""
Notification dispatch service — alert rules engine, Slack, email stub, PagerDuty stub.

POST /api/notifications/dispatch         — dispatch an alert through configured channels
GET  /api/notifications/alert-rules      — list alert rules
POST /api/notifications/alert-rules      — create alert rule
PUT  /api/notifications/alert-rules/{id} — update alert rule
DELETE /api/notifications/alert-rules/{id} — delete alert rule
POST /api/notifications/alert-rules/{id}/toggle — enable/disable
GET  /api/notifications/history          — recent dispatched notifications
POST /api/notifications/test             — test a specific channel (slack/email/pagerduty)
"""
import json
import logging
import os
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ...core.db_utils import get_sync_conn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications")


# ── DB bootstrap ───────────────────────────────────────────────────────────────

def _ensure_tables(conn):
    cur = conn.cursor()
    # notification_config: one row (id='default') holds all webhook credentials.
    # Created here so it exists from first dispatch even before the settings page is visited.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notification_config (
            id TEXT PRIMARY KEY DEFAULT 'default',
            slack_webhook_url   TEXT DEFAULT '',
            pagerduty_key       TEXT DEFAULT '',
            email_from          TEXT DEFAULT '',
            email_smtp_host     TEXT DEFAULT '',
            email_smtp_port     INTEGER DEFAULT 587,
            email_smtp_user     TEXT DEFAULT '',
            email_smtp_pass     TEXT DEFAULT '',
            updated_at          TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        INSERT INTO notification_config (id)
        VALUES ('default')
        ON CONFLICT (id) DO NOTHING
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            condition TEXT NOT NULL,
            channel TEXT NOT NULL,
            threshold FLOAT DEFAULT 0,
            cooldown_minutes INTEGER DEFAULT 60,
            enabled BOOLEAN DEFAULT TRUE,
            last_fired_at TIMESTAMP,
            fire_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notification_history (
            id TEXT PRIMARY KEY,
            rule_id TEXT,
            channel TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT DEFAULT 'sent',
            error_message TEXT DEFAULT '',
            sent_at TIMESTAMP DEFAULT NOW()
        )
    """)
    # Insert default alert rule templates only on first boot (real defaults, not fake data)
    cur.execute("SELECT COUNT(*) FROM alert_rules")
    _cnt = cur.fetchone()
    if (_cnt[0] if _cnt else 0) == 0:
        defaults = [
            (str(uuid.uuid4()), 'Pipeline Failure Alert',   'Fire on any pipeline failure',      'pipeline_failure', 'slack',     0,   60,   True),
            (str(uuid.uuid4()), 'Anomaly Detected',         'ML anomaly score above threshold',   'anomaly',          'slack',     0.8, 120,  True),
            (str(uuid.uuid4()), 'Null Spike Alert',         'Null rate jumps > 20% in a column', 'null_spike',       'slack',     20,  60,   True),
            (str(uuid.uuid4()), 'Row Count Drop',           'Row count drops > 30% vs prior run','row_count_drop',   'slack',     30,  30,   False),
            (str(uuid.uuid4()), 'Cost Threshold Exceeded',  'Daily spend over $50',              'cost_threshold',   'email',     50,  1440, False),
        ]
        for s in defaults:
            cur.execute("""
                INSERT INTO alert_rules (id, name, description, condition, channel, threshold, cooldown_minutes, enabled)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
            """, s)
    conn.commit()


def _get_notification_config(conn) -> dict:
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT slack_webhook_url, email_from, email_smtp_host, email_smtp_port,
                   email_smtp_user, email_smtp_pass, pagerduty_key
            FROM notification_config WHERE id='default'
        """)
        row = cur.fetchone()
        if row:
            return {
                "slack_webhook_url": row[0] or os.getenv("SLACK_WEBHOOK_URL", ""),
                "email_from":        row[1] or "",
                "email_smtp_host":   row[2] or "",
                "email_smtp_port":   row[3] or 587,
                "email_smtp_user":   row[4] or "",
                "email_smtp_pass":   row[5] or "",
                "pagerduty_key":     row[6] or os.getenv("PAGERDUTY_KEY", ""),
            }
    except Exception:
        pass
    return {"slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL", "")}


# ── Channel dispatch helpers ───────────────────────────────────────────────────

def _send_slack(webhook_url: str, subject: str, body: str, severity: str = "info") -> tuple[bool, str]:
    if not webhook_url:
        return False, "No Slack webhook URL configured"
    color_map = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#3b82f6", "success": "#22c55e"}
    color = color_map.get(severity, "#3b82f6")
    payload = {
        "attachments": [{
            "color": color,
            "title": f"🤖 OrchestrAI — {subject}",
            "text": body,
            "footer": "OrchestrAI Alerts",
            "ts": int(datetime.now(timezone.utc).timestamp()),
        }]
    }
    try:
        r = httpx.post(webhook_url, json=payload, timeout=5)
        if r.status_code == 200:
            return True, "Sent"
        return False, f"Slack returned {r.status_code}: {r.text}"
    except Exception as e:
        return False, str(e)


def _send_email(config: dict, to_addr: str, subject: str, body_html: str) -> tuple[bool, str]:
    smtp_host = config.get("email_smtp_host", "")
    if not smtp_host:
        return False, "SMTP not configured — email skipped (stub mode)"
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[OrchestrAI] {subject}"
        msg["From"] = config.get("email_from", "alerts@orchestrai.io")
        msg["To"] = to_addr
        msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP(smtp_host, config.get("email_smtp_port", 587), timeout=10) as s:
            s.starttls()
            if config.get("email_smtp_user") and config.get("email_smtp_pass"):
                s.login(config["email_smtp_user"], config["email_smtp_pass"])
            s.send_message(msg)
        return True, "Email sent"
    except Exception as e:
        return False, f"SMTP error: {e}"


def _send_pagerduty(key: str, subject: str, body: str, severity: str = "warning") -> tuple[bool, str]:
    if not key:
        return False, "PagerDuty key not configured — skipped (stub mode)"
    try:
        payload = {
            "routing_key": key,
            "event_action": "trigger",
            "payload": {
                "summary": f"OrchestrAI: {subject}",
                "severity": "critical" if severity == "critical" else "warning",
                "source": "OrchestrAI",
                "custom_details": {"message": body},
            }
        }
        r = httpx.post("https://events.pagerduty.com/v2/enqueue", json=payload, timeout=5)
        if r.status_code in (200, 202):
            return True, f"PagerDuty incident created: {r.json().get('dedup_key','')}"
        return False, f"PagerDuty returned {r.status_code}"
    except Exception as e:
        return False, str(e)


def _dispatch_notification(channel: str, config: dict, subject: str, body: str, severity: str = "info") -> tuple[bool, str]:
    if channel == "slack":
        return _send_slack(config.get("slack_webhook_url", ""), subject, body, severity)
    elif channel == "email":
        to = config.get("email_from", "admin@orchestrai.io")
        return _send_email(config, to, subject, body)
    elif channel == "pagerduty":
        return _send_pagerduty(config.get("pagerduty_key", ""), subject, body, severity)
    return False, f"Unknown channel: {channel}"


def _record_history(conn, rule_id: Optional[str], channel: str, subject: str, body: str, status: str, error: str = ""):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO notification_history (id, rule_id, channel, subject, body, status, error_message, sent_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
    """, (str(uuid.uuid4()), rule_id, channel, subject, body[:500], status, error[:500]))
    conn.commit()


# ── Pydantic models ────────────────────────────────────────────────────────────

class DispatchRequest(BaseModel):
    subject: str
    body: str
    severity: str = "info"      # info | warning | critical | success
    channels: List[str] = ["slack"]
    rule_id: Optional[str] = None


class AlertRuleRequest(BaseModel):
    name: str
    description: str = ""
    condition: str              # pipeline_failure | anomaly | cost_threshold | null_spike | row_count_drop | custom
    channel: str                # slack | email | pagerduty
    threshold: float = 0
    cooldown_minutes: int = 60
    enabled: bool = True


class TestChannelRequest(BaseModel):
    channel: str                # slack | email | pagerduty


# ── Config endpoint ───────────────────────────────────────────────────────────

@router.get("/config")
def get_notifications_config():
    """Return current notification channel configuration (safe — secrets masked)."""
    try:
        conn = get_sync_conn()
        _ensure_tables(conn)
        config = _get_notification_config(conn)
        conn.close()
        # Mask secrets
        if config.get("pagerduty_key"):
            config["pagerduty_key"] = "••••"
        if config.get("email_smtp_pass"):
            config["email_smtp_pass"] = "••••"
        return {"config": config}
    except Exception as e:
        logger.warning("get_notifications_config error: %s", e)
        return {"config": {"slack_webhook_url": "", "email_from": "", "email_smtp_host": "",
                           "email_smtp_port": 587, "email_smtp_user": "", "pagerduty_key": "",
                           "alert_rules": []}}


# ── Dispatch endpoint ──────────────────────────────────────────────────────────

@router.post("/dispatch")
def dispatch_alert(body: DispatchRequest, background: BackgroundTasks):
    """
    Fire an alert through one or more channels.
    Called by healing agent, quality rules runner, pipeline monitors, etc.
    """
    results = {}
    try:
        conn = get_sync_conn()
        _ensure_tables(conn)
        config = _get_notification_config(conn)

        for channel in body.channels:
            ok, msg = _dispatch_notification(channel, config, body.subject, body.body, body.severity)
            results[channel] = {"ok": ok, "message": msg}
            status = "sent" if ok else "failed"
            _record_history(conn, body.rule_id, channel, body.subject, body.body, status, "" if ok else msg)

        conn.close()
    except Exception as e:
        logger.error(f"dispatch_alert error: {e}")
        return {"results": {}, "error": str(e)}

    return {"results": results}


# ── Alert Rules ────────────────────────────────────────────────────────────────

@router.get("/alert-rules")
def list_alert_rules():
    try:
        conn = get_sync_conn()
        _ensure_tables(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, description, condition, channel, threshold,
                   cooldown_minutes, enabled, last_fired_at, fire_count, created_at
            FROM alert_rules ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        conn.close()
        return {"rules": [
            {
                "id": r[0], "name": r[1], "description": r[2],
                "condition": r[3], "channel": r[4], "threshold": r[5],
                "cooldown_minutes": r[6], "enabled": r[7],
                "last_fired_at": r[8].isoformat() if r[8] else None,
                "fire_count": r[9],
                "created_at": r[10].isoformat() if r[10] else None,
            }
            for r in rows
        ]}
    except Exception as e:
        logger.error("list_alert_rules DB error: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch alert rules: {e}")


@router.post("/alert-rules")
def create_alert_rule(body: AlertRuleRequest):
    rule_id = str(uuid.uuid4())
    conn = get_sync_conn()
    _ensure_tables(conn)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO alert_rules (id, name, description, condition, channel, threshold, cooldown_minutes, enabled)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (rule_id, body.name, body.description, body.condition, body.channel,
          body.threshold, body.cooldown_minutes, body.enabled))
    conn.commit(); conn.close()
    return {"id": rule_id, "message": "Alert rule created"}


@router.put("/alert-rules/{rule_id}")
def update_alert_rule(rule_id: str, body: AlertRuleRequest):
    conn = get_sync_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE alert_rules SET name=%s, description=%s, condition=%s, channel=%s,
            threshold=%s, cooldown_minutes=%s, enabled=%s
        WHERE id=%s
    """, (body.name, body.description, body.condition, body.channel,
          body.threshold, body.cooldown_minutes, body.enabled, rule_id))
    conn.commit(); conn.close()
    return {"message": "Updated"}


@router.delete("/alert-rules/{rule_id}")
def delete_alert_rule(rule_id: str):
    conn = get_sync_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM alert_rules WHERE id=%s", (rule_id,))
    conn.commit(); conn.close()
    return {"message": "Deleted"}


@router.post("/alert-rules/{rule_id}/toggle")
def toggle_alert_rule(rule_id: str):
    conn = get_sync_conn()
    cur = conn.cursor()
    cur.execute("UPDATE alert_rules SET enabled = NOT enabled WHERE id=%s RETURNING enabled", (rule_id,))
    row = cur.fetchone()
    conn.commit(); conn.close()
    return {"enabled": row[0] if row else None}


# ── History ────────────────────────────────────────────────────────────────────

@router.get("/history")
def notification_history(limit: int = 50):
    try:
        conn = get_sync_conn()
        _ensure_tables(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, rule_id, channel, subject, body, status, error_message, sent_at
            FROM notification_history ORDER BY sent_at DESC LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        conn.close()
        return {"history": [
            {"id": r[0], "rule_id": r[1], "channel": r[2],
             "subject": r[3], "body": r[4][:200] if r[4] else "",
             "status": r[5], "error_message": r[6],
             "sent_at": r[7].isoformat() if r[7] else None}
            for r in rows
        ], "total": len(rows)}
    except Exception as e:
        logger.error("notification_history DB error: %s", e)
        return {"history": [], "total": 0}


# ── Test channel ───────────────────────────────────────────────────────────────

@router.post("/test")
def test_channel(body: TestChannelRequest):
    conn = get_sync_conn()
    _ensure_tables(conn)
    config = _get_notification_config(conn)
    conn.close()

    subject = "OrchestrAI — Test Notification"
    msg_body = "✅ This is a test alert from OrchestrAI. Your notification channel is working correctly."

    ok, message = _dispatch_notification(body.channel, config, subject, msg_body, "info")
    return {"success": ok, "channel": body.channel, "message": message}
