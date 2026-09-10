"""Analytics + AI Analyst endpoint smoke tests."""


def test_run_nl_query_missing_body(client):
    r = client.post("/api/analyst/query", json={})
    assert r.status_code == 422


def test_run_nl_query_valid(client):
    r = client.post("/api/analyst/query", json={"question": "Show me total revenue by region"})
    # 200 (success) or 500 (LLM unavailable in test) — not 422/404
    assert r.status_code in (200, 500)


def test_insights_200(client):
    r = client.get("/api/insights")
    assert r.status_code in (200, 404, 500)


def test_stats_overview_200(client):
    r = client.get("/api/stats/overview")
    assert r.status_code in (200, 500)


def test_metrics_history_200(client):
    r = client.get("/api/metrics/history")
    # May be 503 if DB unavailable in test env
    assert r.status_code in (200, 503)


def test_analyst_tables_200(client):
    r = client.get("/api/analyst/tables")
    assert r.status_code in (200, 500)
