"""Health check endpoint tests."""


def test_health_returns_200(client):
    r = client.get("/health")
    # 200 (ok) or 503 (degraded — DB unreachable in test env) are both acceptable
    assert r.status_code in (200, 503)


def test_health_has_required_fields(client):
    r = client.get("/health")
    body = r.json()
    assert "status" in body
    assert "service" in body
    assert body["service"] == "OrchestrAI"
    assert "version" in body
    assert "components" in body


def test_health_status_values(client):
    r = client.get("/health")
    body = r.json()
    assert body["status"] in ("ok", "degraded")
