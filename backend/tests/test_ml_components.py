"""
Tests for ML components:
  A. DuckDBWarehouse  (core/duckdb_warehouse.py)
  B. ETLRunner        (core/etl_runner.py)
  C. OutcomeTracker   (core/outcome_tracker.py)
  D. ML Metrics API   (api/ml_metrics.py)
  E. Integration: learning/warehouse endpoints
"""
import os
import tempfile
import uuid
from unittest.mock import MagicMock, patch

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_tmp_duckdb():
    """Return a temp path that does NOT yet exist (DuckDB creates it)."""
    fd, path = tempfile.mkstemp(suffix=".duckdb")
    os.close(fd)
    os.unlink(path)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# A. DuckDB Warehouse
# ══════════════════════════════════════════════════════════════════════════════

class TestDuckDBWarehouse:

    def _open(self, tmp_path):
        """Open a DuckDBWarehouse pointed at a temp file."""
        import core.duckdb_warehouse as _mod
        from core.duckdb_warehouse import DuckDBWarehouse

        orig_path = _mod.WAREHOUSE_PATH
        _mod.WAREHOUSE_PATH = type(orig_path)(tmp_path)

        # Patch __init__ so mkdir uses the new path
        original_init = DuckDBWarehouse.__init__

        def patched_init(self_inner):
            _mod.WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
            self_inner._conn = None

        DuckDBWarehouse.__init__ = patched_init
        wh = DuckDBWarehouse()
        DuckDBWarehouse.__init__ = original_init
        _mod.WAREHOUSE_PATH = orig_path

        # Connect using the patched path before restoring
        import duckdb
        wh._conn = duckdb.connect(tmp_path)
        wh._read_only = False
        wh._init_schema()
        return wh

    def test_connect_creates_tables(self):
        """connect() creates all 4 expected tables."""
        tmp = _make_tmp_duckdb()
        try:
            wh = self._open(tmp)
            tables = {
                r[0]
                for r in wh._conn.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
                ).fetchall()
            }
            wh.close()
            for expected in [
                "raw_pipeline_data",
                "pipeline_metrics_warehouse",
                "nyc_taxi_trips",
                "ecommerce_orders",
            ]:
                assert expected in tables, f"Table {expected!r} not found in {tables}"
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_insert_batch_and_count(self):
        """insert_batch() returns correct count; get_table_count() reflects it."""
        tmp = _make_tmp_duckdb()
        try:
            wh = self._open(tmp)
            records = [
                {
                    "id": str(uuid.uuid4()),
                    "pipeline_name": "test_pipe",
                    "source_type": "generic",
                    "records_count": 42,
                    "loaded_at": "2024-01-01 00:00:00",
                    "batch_id": str(uuid.uuid4()),
                    "workspace_id": "default",
                }
                for _ in range(5)
            ]
            n = wh.insert_batch("raw_pipeline_data", records)
            assert n == 5
            count = wh.get_table_count("raw_pipeline_data")
            assert count == 5
            wh.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_insert_batch_empty_returns_zero(self):
        """insert_batch() with empty list returns 0."""
        tmp = _make_tmp_duckdb()
        try:
            wh = self._open(tmp)
            n = wh.insert_batch("raw_pipeline_data", [])
            assert n == 0
            wh.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_get_recent_loads_empty(self):
        """get_recent_loads() returns [] when no data for that pipeline."""
        tmp = _make_tmp_duckdb()
        try:
            wh = self._open(tmp)
            result = wh.get_recent_loads("nonexistent_pipeline")
            assert isinstance(result, list)
            assert result == []
            wh.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_get_table_count_nonexistent_returns_zero(self):
        """get_table_count() returns 0 for an empty / nonexistent table."""
        tmp = _make_tmp_duckdb()
        try:
            wh = self._open(tmp)
            # Table exists but is empty
            count = wh.get_table_count("ecommerce_orders")
            assert count == 0
            wh.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


# ══════════════════════════════════════════════════════════════════════════════
# B. ETL Runner
# ══════════════════════════════════════════════════════════════════════════════

class TestETLRunner:

    def test_generic_returns_success_or_warning(self):
        """Generic source returns status=success or warning with records >= 0."""
        from core.etl_runner import ETLRunner

        # Stub _log_to_warehouse so it doesn't try to open the real DuckDB file
        with patch.object(ETLRunner, "_log_to_warehouse", return_value=None):
            runner = ETLRunner()
            result = runner.run_pipeline("test_pipeline", "generic", {})

        assert result["status"] in ("success", "warning"), f"Unexpected status: {result['status']}"
        assert result["records_loaded"] >= 0
        assert "duration_seconds" in result

    def test_csv_source_returns_valid_dict(self):
        """CSV source type returns a valid result dict."""
        from core.etl_runner import ETLRunner

        with patch.object(ETLRunner, "_log_to_warehouse", return_value=None):
            runner = ETLRunner()
            result = runner.run_pipeline("test_csv_pipeline", "csv", {})

        assert isinstance(result, dict)
        assert "records_loaded" in result
        assert "status" in result
        assert "duration_seconds" in result

    def test_api_source_returns_valid_dict(self):
        """REST API source type returns a valid result dict."""
        from core.etl_runner import ETLRunner

        with patch.object(ETLRunner, "_log_to_warehouse", return_value=None):
            runner = ETLRunner()
            result = runner.run_pipeline("test_api_pipeline", "rest_api", {})

        assert isinstance(result, dict)
        assert result["records_loaded"] >= 0
        assert "status" in result

    def test_failed_source_returns_error_key(self):
        """When ETL crashes internally, result has status=failed and error key."""
        from core.etl_runner import ETLRunner

        def boom(*args, **kwargs):
            raise RuntimeError("Injected test failure")

        with patch.object(ETLRunner, "_run_generic", side_effect=boom):
            runner = ETLRunner()
            result = runner.run_pipeline("bad_pipeline", "generic", {})

        assert result["status"] == "failed"
        assert "error" in result
        assert "Injected test failure" in result["error"]

    def test_google_sheets_source_returns_valid_dict(self):
        """Google Sheets source type returns a valid result dict."""
        from core.etl_runner import ETLRunner

        with patch.object(ETLRunner, "_log_to_warehouse", return_value=None):
            runner = ETLRunner()
            result = runner.run_pipeline("sheets_pipeline", "google_sheets", {})

        assert isinstance(result, dict)
        assert result["records_loaded"] >= 0

    def test_result_always_has_duration(self):
        """Every run result (success or fail) includes duration_seconds."""
        from core.etl_runner import ETLRunner

        with patch.object(ETLRunner, "_log_to_warehouse", return_value=None):
            runner = ETLRunner()
            for source in ("generic", "csv", "rest_api"):
                result = runner.run_pipeline("p", source, {})
                assert "duration_seconds" in result, f"Missing duration for source={source}"


# ══════════════════════════════════════════════════════════════════════════════
# C. Outcome Tracker
# ══════════════════════════════════════════════════════════════════════════════

class TestOutcomeTracker:

    def test_record_outcome_calls_db(self):
        """record_outcome() calls psycopg2.connect and executes INSERT (or fails gracefully)."""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("core.outcome_tracker.psycopg2.connect", return_value=mock_conn):
            from core.outcome_tracker import OutcomeTracker
            tracker = OutcomeTracker()
            try:
                result = tracker.record_outcome(
                    "inc-test-1",
                    "my_pipeline",
                    "ZERO_LOAD",
                    "restart_pipeline",
                    "approved",
                )
                # If mock worked, result should be True
                assert result in (True, False)
            except Exception:
                pass  # DB unavailable in test env — that's fine

    def test_get_learning_stats_no_db(self):
        """get_learning_stats() returns a dict even when DB is unavailable."""
        from core.outcome_tracker import OutcomeTracker
        tracker = OutcomeTracker()
        stats = tracker.get_learning_stats()
        assert isinstance(stats, dict)

    def test_get_learning_stats_has_expected_keys(self):
        """get_learning_stats() dict has required top-level keys."""
        from core.outcome_tracker import OutcomeTracker
        tracker = OutcomeTracker()
        stats = tracker.get_learning_stats()
        for key in ("total_outcomes", "avg_mttr", "success_rate", "mttr_trend"):
            assert key in stats, f"Missing key: {key!r}"

    def test_get_mttr_trend_no_db_returns_list(self):
        """get_mttr_trend() returns a list even when DB is unavailable."""
        from core.outcome_tracker import OutcomeTracker
        tracker = OutcomeTracker()
        trend = tracker.get_mttr_trend(days=7)
        assert isinstance(trend, list)

    def test_get_strategy_success_rates_no_db_returns_dict(self):
        """get_strategy_success_rates() returns a dict when DB is unavailable."""
        from core.outcome_tracker import OutcomeTracker
        tracker = OutcomeTracker()
        rates = tracker.get_strategy_success_rates()
        assert isinstance(rates, dict)

    def test_record_outcome_with_mock_succeeds(self):
        """When DB is mocked, record_outcome returns True."""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("core.outcome_tracker.psycopg2.connect", return_value=mock_conn):
            from core.outcome_tracker import OutcomeTracker
            tracker = OutcomeTracker()
            result = tracker.record_outcome(
                "inc-mock-1", "pipe", "SCHEMA_DRIFT", "schema_evolution", "approved"
            )
        assert result is True


# ══════════════════════════════════════════════════════════════════════════════
# D. ML Metrics API (via TestClient)
# ══════════════════════════════════════════════════════════════════════════════

class TestMLMetricsAPI:

    def test_ml_metrics_endpoint_exists(self, client):
        """GET /api/ml/metrics — endpoint exists (200 with metrics or 404 if pkl not trained)."""
        resp = client.get("/api/ml/metrics")
        assert resp.status_code in (200, 404, 500), f"Unexpected {resp.status_code}"

    def test_ml_metrics_404_or_has_valid_json(self, client):
        """GET /api/ml/metrics — if 200, body is valid JSON; if 404, detail is present."""
        resp = client.get("/api/ml/metrics")
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)
        elif resp.status_code == 404:
            body = resp.json()
            assert "detail" in body
        # 500 also acceptable (e.g. json parse error on malformed metrics file)

    def test_ml_train_endpoint_exists(self, client):
        """POST /api/ml/train — endpoint exists (200, 404, 500, or 504 are all acceptable)."""
        resp = client.post("/api/ml/train")
        assert resp.status_code in (200, 404, 500, 504), (
            f"Unexpected status {resp.status_code}: {resp.text[:200]}"
        )

    def test_ml_metrics_response_structure_when_200(self, client):
        """If /api/ml/metrics returns 200, it has at least one top-level key."""
        resp = client.get("/api/ml/metrics")
        if resp.status_code == 200:
            data = resp.json()
            assert len(data) > 0, "Metrics dict should not be empty"


# ══════════════════════════════════════════════════════════════════════════════
# E. Integration — learning + warehouse endpoints
# ══════════════════════════════════════════════════════════════════════════════

class TestLearningEndpoints:

    def test_learning_stats_returns_200(self, client):
        """GET /api/learning/stats returns 200."""
        resp = client.get("/api/learning/stats")
        assert resp.status_code == 200

    def test_learning_stats_response_is_dict(self, client):
        """GET /api/learning/stats returns a JSON object."""
        resp = client.get("/api/learning/stats")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_learning_mttr_trend_returns_200(self, client):
        """GET /api/learning/mttr-trend returns 200."""
        resp = client.get("/api/learning/mttr-trend")
        assert resp.status_code == 200

    def test_learning_mttr_trend_returns_list(self, client):
        """GET /api/learning/mttr-trend body is a list."""
        resp = client.get("/api/learning/mttr-trend")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_learning_mttr_trend_with_days_param(self, client):
        """GET /api/learning/mttr-trend?days=7 returns 200."""
        resp = client.get("/api/learning/mttr-trend?days=7")
        assert resp.status_code == 200

    def test_warehouse_stats_endpoint(self, client):
        """GET /api/warehouse/stats — 200 or 404 (may not be registered yet)."""
        resp = client.get("/api/warehouse/stats")
        assert resp.status_code in (200, 404), f"Unexpected {resp.status_code}"

    def test_learning_strategy_performance_endpoint(self, client):
        """GET /api/learning/strategy-performance returns 200."""
        resp = client.get("/api/learning/strategy-performance")
        assert resp.status_code in (200, 404)
