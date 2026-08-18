"""
Notification utilities — Slack webhook, email stubs.

Set SLACK_WEBHOOK_URL in your .env to enable Slack alerts.
Example: SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../xxx

The same pattern can be extended to PagerDuty, MS Teams, or email (SendGrid).
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


def send_slack_incident_alert(
    pipeline_name: str,
    anomaly_type: str,
    incident_id: str,
    confidence: Optional[float] = None,
    root_cause: Optional[str] = None,
    app_url: str = "http://localhost:3001",
) -> bool:
    """
    Post an incident alert to the configured Slack webhook.
    Returns True on success, False on failure (non-blocking).
    """
    if not SLACK_WEBHOOK_URL:
        logger.debug("SLACK_WEBHOOK_URL not set — skipping Slack notification")
        return False

    confidence_pct = f"{round(confidence * 100)}%" if confidence else "—"
    approval_url = f"{app_url}/approvals"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🚨 OrchestrAI Incident Detected", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Pipeline:*\n{pipeline_name}"},
                {"type": "mrkdwn", "text": f"*Anomaly:*\n{anomaly_type.upper().replace('_', ' ')}"},
                {"type": "mrkdwn", "text": f"*Confidence:*\n{confidence_pct}"},
                {"type": "mrkdwn", "text": f"*Incident ID:*\n`{incident_id[:8]}...`"},
            ],
        },
    ]

    if root_cause:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Root Cause:*\n{root_cause[:200]}"},
        })

    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Review & Approve Fix", "emoji": True},
                "url": approval_url,
                "style": "primary",
            },
        ],
    })

    payload = {
        "text": f"🚨 Incident on *{pipeline_name}* — {anomaly_type.upper()}",
        "blocks": blocks,
    }

    try:
        resp = httpx.post(SLACK_WEBHOOK_URL, json=payload, timeout=5.0)
        resp.raise_for_status()
        logger.info("Slack alert sent for incident %s", incident_id)
        return True
    except Exception as e:
        logger.warning("Slack notification failed: %s", e)
        return False


def send_slack_heal_result(
    pipeline_name: str,
    incident_id: str,
    success: bool,
    models_succeeded: int = 0,
    app_url: str = "http://localhost:3001",
) -> bool:
    """Post a healing completion notification."""
    if not SLACK_WEBHOOK_URL:
        return False

    emoji = "✅" if success else "❌"
    status = "Healed successfully" if success else "Healing failed"

    payload = {
        "text": f"{emoji} *{pipeline_name}* — {status}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{pipeline_name}* — {status}\nIncident `{incident_id[:8]}...` | <{app_url}/approvals|View in OrchestrAI>",
                },
            }
        ],
    }

    try:
        resp = httpx.post(SLACK_WEBHOOK_URL, json=payload, timeout=5.0)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.warning("Slack heal-result notification failed: %s", e)
        return False
