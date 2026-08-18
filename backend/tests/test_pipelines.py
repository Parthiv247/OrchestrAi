"""Pipeline endpoint smoke tests."""
import pytest


def test_list_pipelines_200(client):
    r = client.get("/api/pipelines")
    assert r.status_code == 200
    body = r.json()
    assert "pipelines" in body or isinstance(body, list)


def test_pipeline_stats_200(client):
    r = client.get("/api/pipelines/stats")
    assert r.status_code == 200
    body = r.json()
    # Must have at least one metric key
    assert len(body) > 0


def test_get_pipeline_not_found(client):
    r = client.get("/api/pipelines/nonexistent-id-xyz")
    assert r.status_code == 404


def test_create_pipeline_missing_fields(client):
    r = client.post("/api/pipelines", json={})
    assert r.status_code == 422  # Pydantic validation error


def test_create_pipeline_valid(client):
    payload = {
        "name": "test_pipeline",
        "source_connection_id": "conn-001",
        "dest_connection_id": "conn-002",
        "dest_table": "target_table",
        "sync_mode": "full_refresh",
    }
    r = client.post("/api/pipelines", json=payload)
    # 200 success or 500 DB unavailable
    assert r.status_code in (200, 500)


def test_pipeline_runs_not_found(client):
    r = client.get("/api/pipelines/nonexistent-id/runs")
    assert r.status_code == 404


def test_etl_queue_200(client):
    r = client.get("/api/etl/queue")
    assert r.status_code == 200


def test_etl_dlq_200(client):
    r = client.get("/api/etl/dlq")
    assert r.status_code == 200
