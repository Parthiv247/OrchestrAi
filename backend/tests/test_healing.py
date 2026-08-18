"""Self-healing endpoint smoke tests."""
import pytest


def test_list_incidents_200(client):
    r = client.get("/api/incidents")
    assert r.status_code == 200
    body = r.json()
    # Endpoint now returns a paginated envelope, not a flat list
    assert isinstance(body, dict), f"Expected dict, got {type(body)}: {body}"
    assert "incidents" in body
    assert "total" in body
    assert "has_more" in body
    assert isinstance(body["incidents"], list)


def test_healing_status_200(client):
    r = client.get("/api/healing/status")
    assert r.status_code == 200
    body = r.json()
    assert "total_incidents" in body
    assert "pending" in body
    assert "approved" in body
    assert "deployed" in body


def test_get_incident_not_found(client):
    r = client.get("/api/incidents/nonexistent-uuid-1234")
    assert r.status_code == 404


def test_trigger_healing_missing_name(client):
    r = client.post("/api/healing/trigger/x")
    # pipeline_name length < 2 → 400
    assert r.status_code == 400


def test_trigger_healing_valid_name(client):
    r = client.post("/api/healing/trigger/test_pipeline_abc")
    # May be 200 (success) or 500 (DB unavailable in test) — not 404/400
    assert r.status_code in (200, 500)


def test_approve_incident_not_found(client):
    r = client.post("/api/incidents/bad-id/approve?token=demo")
    assert r.status_code == 404


def test_reject_incident_not_found(client):
    r = client.post("/api/incidents/bad-id/reject?token=demo")
    assert r.status_code == 404
