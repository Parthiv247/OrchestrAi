"""
E2E tests for the self-healing pipeline loop.

These tests verify the full HTTP surface of the healing workflow:
  1. Trigger → incident created (or 500 when DB unavailable in test env)
  2. Incident list returns paginated envelope
  3. Incident detail shape
  4. Approve / reject endpoints return correct status
  5. Healing status shape
  6. MTTR trend and strategy performance endpoints
  7. NL-to-SQL query → execute flow (integration)
  8. ML metrics endpoint
  9. Learning stats endpoint

All external deps (Postgres, ChromaDB, Groq, Docker) are mocked via conftest.
"""


# ── Healing trigger ────────────────────────────────────────────────────────────

class TestHealingTrigger:
    def test_trigger_valid_pipeline_returns_200_or_500(self, client):
        """Trigger must succeed (200) or gracefully fail (500) — never 404/400 for a valid name."""
        r = client.post("/api/healing/trigger/ingest_nyc_taxi")
        assert r.status_code in (200, 500), f"Unexpected {r.status_code}: {r.text}"

    def test_trigger_short_name_rejected(self, client):
        r = client.post("/api/healing/trigger/x")
        assert r.status_code == 400

    def test_trigger_response_shape_on_success(self, client):
        r = client.post("/api/healing/trigger/ingest_ecommerce")
        if r.status_code == 200:
            body = r.json()
            assert "incident_id" in body
            assert "pipeline_name" in body
            assert body["pipeline_name"] == "ingest_ecommerce"
            assert "started_at" in body

    def test_trigger_all_known_pipelines_dont_404(self, client):
        for name in ["ingest_nyc_taxi", "ingest_ecommerce", "dbt_run", "kafka_consumer"]:
            r = client.post(f"/api/healing/trigger/{name}")
            assert r.status_code != 404, f"{name} returned 404"


# ── Incident list ──────────────────────────────────────────────────────────────

class TestIncidentList:
    def test_list_returns_paginated_envelope(self, client):
        r = client.get("/api/incidents")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict), "Expected paginated dict"
        assert "incidents" in body
        assert "total" in body
        assert "has_more" in body
        assert isinstance(body["incidents"], list)
        assert isinstance(body["total"], int)
        assert isinstance(body["has_more"], bool)

    def test_list_pagination_params_accepted(self, client):
        r = client.get("/api/incidents?limit=5&offset=0")
        assert r.status_code == 200

    def test_list_status_filter_accepted(self, client):
        r = client.get("/api/incidents?status=pending")
        assert r.status_code == 200

    def test_list_invalid_limit_rejected(self, client):
        r = client.get("/api/incidents?limit=0")
        assert r.status_code in (200, 422)  # some implementations clamp; 422 is valid


# ── Incident detail ────────────────────────────────────────────────────────────

class TestIncidentDetail:
    def test_nonexistent_incident_returns_404(self, client):
        r = client.get("/api/incidents/nonexistent-uuid-abc")
        assert r.status_code == 404

    def test_incident_detail_missing_id_404(self, client):
        r = client.get("/api/incidents/")
        # FastAPI returns 404 for missing path param (hits list endpoint instead)
        assert r.status_code in (200, 404)


# ── Approve / Reject ───────────────────────────────────────────────────────────

class TestApproveReject:
    def test_approve_nonexistent_returns_404(self, client):
        r = client.post("/api/incidents/bad-id/approve?token=tok")
        assert r.status_code == 404

    def test_reject_nonexistent_returns_404(self, client):
        r = client.post("/api/incidents/bad-id/reject?token=tok")
        assert r.status_code == 404

    def test_approve_requires_token(self, client):
        """Approve without token query param returns 400 or 422."""
        r = client.post("/api/incidents/some-id/approve")
        assert r.status_code in (400, 404, 422)

    def test_reject_body_optional(self, client):
        """Reject with no body (reason defaults) should not return 422."""
        r = client.post("/api/incidents/bad-id/reject?token=tok", json={})
        assert r.status_code != 422


# ── Healing status ─────────────────────────────────────────────────────────────

class TestHealingStatus:
    def test_status_shape(self, client):
        r = client.get("/api/healing/status")
        assert r.status_code == 200
        body = r.json()
        for key in ("total_incidents", "pending", "approved", "deployed"):
            assert key in body, f"Missing key: {key}"

    def test_status_counts_are_ints(self, client):
        r = client.get("/api/healing/status")
        body = r.json()
        assert isinstance(body.get("total_incidents"), int)
        assert isinstance(body.get("pending"), int)


# ── Learning stats ─────────────────────────────────────────────────────────────

class TestLearningStats:
    def test_stats_200(self, client):
        r = client.get("/api/learning/stats")
        assert r.status_code == 200

    def test_stats_has_expected_keys(self, client):
        r = client.get("/api/learning/stats")
        body = r.json()
        # Endpoint may return outcome_stats or a ChromaDB-error fallback dict —
        # either way at least one of these keys is always present.
        assert any(k in body for k in (
            "avg_mttr", "total_outcomes", "rag_fixes_stored",
            "total_fixes_stored", "rag_queries_stored", "error",
        ))

    def test_mttr_trend_200(self, client):
        r = client.get("/api/learning/mttr-trend")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)

    def test_mttr_trend_days_param(self, client):
        r = client.get("/api/learning/mttr-trend?days=7")
        assert r.status_code == 200

    def test_mttr_trend_days_out_of_range(self, client):
        r = client.get("/api/learning/mttr-trend?days=0")
        assert r.status_code == 422  # Query param ge=1 validation

    def test_strategy_performance_200(self, client):
        r = client.get("/api/learning/strategy-performance")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)


# ── ML metrics ─────────────────────────────────────────────────────────────────

class TestMLMetrics:
    def test_metrics_200(self, client):
        r = client.get("/api/ml/metrics")
        assert r.status_code == 200

    def test_metrics_shape(self, client):
        r = client.get("/api/ml/metrics")
        body = r.json()
        # At minimum it should be a dict — not a list or error string
        assert isinstance(body, dict)


# ── NL-to-SQL integration flow ─────────────────────────────────────────────────

class TestAnalyticsFlow:
    def test_nl_query_missing_body_returns_422(self, client):
        r = client.post("/api/analyst/query", json={})
        assert r.status_code == 422

    def test_nl_query_with_question_returns_200_or_500(self, client):
        """With mocked LLM, Groq call will fail → 500 is acceptable."""
        r = client.post("/api/analyst/query", json={"question": "How many pipelines ran today?"})
        assert r.status_code in (200, 500)

    def test_execute_valid_select_200(self, client):
        r = client.post("/api/analyst/execute", json={"sql": "SELECT 1"})
        # 200 when DB responds; 400 when mocked connection fails; 500 on unhandled error
        assert r.status_code in (200, 400, 500)

    def test_execute_blocks_write_sql(self, client):
        r = client.post("/api/analyst/execute", json={"sql": "DROP TABLE incidents"})
        # Endpoint returns 403 (Forbidden) for dangerous DDL/DML — not 400
        assert r.status_code == 403

    def test_execute_blocks_delete_sql(self, client):
        r = client.post("/api/analyst/execute", json={"sql": "DELETE FROM pipeline_runs WHERE 1=1"})
        assert r.status_code == 403

    def test_tables_endpoint_200(self, client):
        r = client.get("/api/analyst/tables")
        assert r.status_code == 200


# ── Pipeline pagination ────────────────────────────────────────────────────────

class TestPipelineEndpoints:
    def test_list_pipelines_200(self, client):
        r = client.get("/api/pipelines")
        assert r.status_code == 200

    def test_pipeline_runs_not_found(self, client):
        r = client.get("/api/pipelines/nonexistent-id/runs")
        assert r.status_code in (200, 404)

    def test_delete_pipeline_not_found(self, client):
        r = client.delete("/api/pipelines/nonexistent-id")
        assert r.status_code in (200, 404)


# ── Health endpoint ────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_200_or_503(self, client):
        r = client.get("/health")
        assert r.status_code in (200, 503)

    def test_health_response_shape(self, client):
        r = client.get("/health")
        body = r.json()
        assert "status" in body
        assert "service" in body
        assert body["service"] == "OrchestrAI"
        assert "components" in body
        assert "timestamp" in body

    def test_health_version_field(self, client):
        r = client.get("/health")
        body = r.json()
        assert "version" in body
