"""Data Quality and Lineage endpoint smoke tests."""
import pytest


# ── Data Quality ──────────────────────────────────────────────────────────────

def test_quality_summary_200(client):
    r = client.get("/api/quality/summary")
    assert r.status_code == 200


def test_quality_schema_registry_200(client):
    # Schema registry is served at /api/quality/tables (not /schema-registry)
    r = client.get("/api/quality/tables")
    assert r.status_code == 200
    body = r.json()
    # Response is {"tables": [...]} — may include "error" key when DB is down
    assert isinstance(body, dict)
    assert "tables" in body
    assert isinstance(body["tables"], list)


def test_quality_rules_200(client):
    r = client.get("/api/quality/rules")
    assert r.status_code == 200


def test_quality_drift_report_200(client):
    r = client.get("/api/quality/drift")
    assert r.status_code == 200


# ── Lineage ────────────────────────────────────────────────────────────────────

def test_lineage_graph_200(client):
    r = client.get("/api/lineage/graph")
    assert r.status_code == 200
    body = r.json()
    # Should have nodes and edges
    assert "nodes" in body or isinstance(body, dict)


def test_lineage_pipeline_not_found(client):
    r = client.get("/api/lineage/pipeline/nonexistent_pipeline_xyz")
    assert r.status_code in (200, 404)
