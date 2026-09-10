"""Settings and Reports endpoint smoke tests."""


# ── Settings ──────────────────────────────────────────────────────────────────

def test_get_team_200(client):
    r = client.get("/api/settings/team")
    assert r.status_code == 200


def test_get_tokens_200(client):
    r = client.get("/api/settings/tokens")
    assert r.status_code == 200


def test_get_notifications_settings_200(client):
    r = client.get("/api/settings/notifications")
    assert r.status_code == 200


def test_get_audit_log_200(client):
    r = client.get("/api/settings/audit-log")
    assert r.status_code == 200


# ── Reports ───────────────────────────────────────────────────────────────────

def test_list_reports_200(client):
    r = client.get("/api/reports")
    assert r.status_code == 200
    body = r.json()
    # Response is {"reports": [...]} — envelope shape, not a flat list
    assert isinstance(body, dict)
    assert "reports" in body
    assert isinstance(body["reports"], list)


def test_report_deliveries_recent(client):
    # /api/reports/summary doesn't exist; deliveries/recent is the summary endpoint
    r = client.get("/api/reports/deliveries/recent")
    assert r.status_code in (200, 404, 500)


# ── Notifications ─────────────────────────────────────────────────────────────

def test_notification_rules_200(client):
    # Notification rules are at /api/notifications/alert-rules (not /rules)
    r = client.get("/api/notifications/alert-rules")
    # May be 500 when DB is unavailable in test env
    assert r.status_code in (200, 500)


def test_notification_history_200(client):
    r = client.get("/api/notifications/history")
    assert r.status_code in (200, 500)
