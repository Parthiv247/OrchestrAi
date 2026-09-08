"""
MonitoringAgent — Watches all pipelines via rule-based checks + Isolation Forest ML.

Supported anomaly types (2025 ETL-complete):
  ZERO_LOAD, ROW_COUNT_DROP, NULL_SPIKE, PIPELINE_DELAY, CONSECUTIVE_FAILURES,
  SCHEMA_DRIFT, CDC_LAG, SLA_BREACH, DATA_TYPE_MISMATCH,
  INCREMENTAL_SYNC_FAILURE, RATE_LIMIT_HIT, CASCADING_FAILURE,
  DUPLICATE_SPIKE, PARTITION_SKEW, CHECKPOINT_FAILURE

Multi-database awareness: PostgreSQL, Snowflake, BigQuery, MySQL, MongoDB,
Redshift, DuckDB — error signatures are normalised to the same anomaly types.
"""
import os
import pickle
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import psycopg2
import psycopg2.extras

try:
    import numpy as np
    from sklearn.ensemble import IsolationForest, GradientBoostingClassifier
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from .state import HealingAgentState

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST", "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname":   os.getenv("POSTGRES_DB", "orchestrai"),
    "user":     os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}

MODEL_PATH      = Path(__file__).parent.parent.parent.parent / "ml" / "isolation_forest.pkl"
SCALER_PATH     = Path(__file__).parent.parent.parent.parent / "ml" / "scaler.pkl"
CLASSIFIER_PATH = Path(__file__).parent.parent.parent.parent / "ml" / "anomaly_classifier.pkl"
LABEL_ENCODER_PATH = Path(__file__).parent.parent.parent.parent / "ml" / "label_encoder.pkl"

PIPELINE_NAMES = ["ingest_nyc_taxi", "ingest_ecommerce", "dbt_run", "kafka_consumer"]

# ── Thresholds ─────────────────────────────────────────────────────────────────
ROW_DROP_THRESHOLD     = 0.20   # >20% drop vs 7-day avg
NULL_SPIKE_THRESHOLD   = 0.10   # >10% nulls when baseline <2%
DELAY_MULTIPLIER       = 2.0    # duration > 2x avg
ANOMALY_SCORE_THRESHOLD = 0.0   # IsolationForest.decision_function < 0 → outlier
CONSECUTIVE_FAILURES   = 2      # same pipeline failed N times in a row
DUPLICATE_SPIKE_RATIO  = 0.05   # >5% duplicate rate vs baseline
CDC_LAG_SECONDS        = 300    # CDC offset > 5 minutes = lagged
SLA_BREACH_MULTIPLIER  = 3.0    # duration > 3x SLA target
PARTITION_SKEW_RATIO   = 5.0    # max_partition_rows / avg_partition_rows > 5x

# SLA targets per pipeline (seconds)
PIPELINE_SLA: Dict[str, int] = {
    "ingest_nyc_taxi":  1800,   # 30 min
    "ingest_ecommerce": 900,    # 15 min
    "dbt_run":          3600,   # 60 min
    "kafka_consumer":   300,    # 5 min
}

# Multi-DB error signature → anomaly type mapping
DB_ERROR_SIGNATURES: List[Tuple[str, str]] = [
    # PostgreSQL
    ("could not connect to server",          "ZERO_LOAD"),
    ("SSL connection has been closed",        "ZERO_LOAD"),
    ("connection refused",                    "ZERO_LOAD"),
    ("too many connections",                  "RATE_LIMIT_HIT"),
    ("canceling statement due to conflict",   "PIPELINE_DELAY"),
    ("deadlock detected",                     "CONSECUTIVE_FAILURES"),
    ("out of shared memory",                  "PIPELINE_DELAY"),
    ("duplicate key value violates",          "DUPLICATE_SPIKE"),
    # Snowflake
    ("query result expired",                  "PIPELINE_DELAY"),
    ("warehouse suspended",                   "RATE_LIMIT_HIT"),
    ("account does not have enough credits",  "RATE_LIMIT_HIT"),
    ("stream has become stale",               "CDC_LAG"),
    ("query exceeded memory limit",           "PIPELINE_DELAY"),
    ("schema evolution",                      "SCHEMA_DRIFT"),
    # BigQuery
    ("quota exceeded",                        "RATE_LIMIT_HIT"),
    ("not found: dataset",                    "ZERO_LOAD"),
    ("resources exceeded during query",       "PIPELINE_DELAY"),
    ("streaming buffer not available",        "CDC_LAG"),
    ("schema mismatch",                       "SCHEMA_DRIFT"),
    # MySQL / RDS
    ("max_allowed_packet",                    "PIPELINE_DELAY"),
    ("lock wait timeout exceeded",            "CONSECUTIVE_FAILURES"),
    ("table is full",                         "RATE_LIMIT_HIT"),
    ("binlog format is not row",              "CDC_LAG"),
    # MongoDB
    ("cursor id not found",                   "PIPELINE_DELAY"),
    ("oplog is too small",                    "CDC_LAG"),
    ("changestream cursor timeout",           "CDC_LAG"),
    ("write conflict",                        "CONSECUTIVE_FAILURES"),
    # Redshift
    ("stl_load_errors",                       "DATA_TYPE_MISMATCH"),
    ("permission denied for relation",        "ZERO_LOAD"),
    ("disk full",                             "RATE_LIMIT_HIT"),
    # DuckDB
    ("catalog error",                         "SCHEMA_DRIFT"),
    ("out of memory error",                   "PIPELINE_DELAY"),
    # Kafka / Debezium
    ("offset out of range",                   "CHECKPOINT_FAILURE"),
    ("consumer group rebalance",              "INCREMENTAL_SYNC_FAILURE"),
    ("transaction marker",                    "DATA_TYPE_MISMATCH"),
    # Generic
    ("connection timed out",                  "ZERO_LOAD"),
    ("read timeout",                          "PIPELINE_DELAY"),
    ("ssl: wrong version number",             "ZERO_LOAD"),
    ("incremental load",                      "INCREMENTAL_SYNC_FAILURE"),
]


class MonitoringAgent:
    """Continuously watches all pipelines and detects anomalies using rules + ML."""

    def __init__(self):
        self._model: Optional[Any] = None
        self._scaler: Optional[Any] = None
        self._classifier: Optional[Any] = None
        self._label_encoder: Optional[Any] = None
        self._load_model()

    # ── Public API ─────────────────────────────────────────────────────────────

    def check_pipeline(self, pipeline_name: str) -> Optional[HealingAgentState]:
        """Run all checks for one pipeline. Returns HealingAgentState if anomaly found."""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.set_session(autocommit=True)
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                result = self._run_checks(cur, pipeline_name)
            conn.close()
            return result
        except Exception as e:
            logger.error("MonitoringAgent.check_pipeline error for %s: %s", pipeline_name, e)
            return self._make_state(pipeline_name, "DB_ERROR", {"error": str(e)})

    def run_all_checks(self) -> List[HealingAgentState]:
        """Check every pipeline; return list of anomalous states."""
        anomalies = []
        for name in PIPELINE_NAMES:
            state = self.check_pipeline(name)
            if state is not None:
                anomalies.append(state)
        return anomalies

    def classify_error_message(self, error_msg: str) -> str:
        """Normalise DB-specific error messages to a standard anomaly type."""
        if not error_msg:
            return "UNKNOWN"
        lower = error_msg.lower()
        for signature, anomaly_type in DB_ERROR_SIGNATURES:
            if signature in lower:
                return anomaly_type
        return "CONSECUTIVE_FAILURES"

    def train_model(self) -> bool:
        """Train Isolation Forest on last 30 days of pipeline_runs."""
        if not HAS_SKLEARN:
            logger.warning("scikit-learn not installed — skipping model training")
            return False
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT records_loaded, records_failed, records_ingested,
                           EXTRACT(EPOCH FROM (completed_at - started_at)) AS duration,
                           EXTRACT(HOUR FROM started_at) AS hour_of_day,
                           EXTRACT(DOW FROM started_at) AS day_of_week,
                           CASE WHEN status = 'success' THEN 1 ELSE 0 END AS success_flag,
                           CASE WHEN records_loaded > 0
                                THEN records_failed::float / records_loaded
                                ELSE 0 END AS fail_rate
                    FROM pipeline_runs
                    WHERE started_at >= NOW() - INTERVAL '30 days'
                      AND completed_at IS NOT NULL
                    ORDER BY started_at
                """)
                rows = cur.fetchall()
            conn.close()

            if len(rows) < 10:
                logger.warning("Not enough data to train (%d rows)", len(rows))
                return False

            X = np.array([[
                r[0] or 0, r[1] or 0, r[2] or 0,
                r[3] or 0, r[4] or 9, r[5] or 0, r[6], r[7] or 0,
            ] for r in rows], dtype=float)

            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            model = IsolationForest(contamination=0.08, random_state=42, n_estimators=200, max_samples="auto")
            model.fit(X_scaled)

            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(MODEL_PATH, "wb") as f:
                pickle.dump(model, f)
            with open(SCALER_PATH, "wb") as f:
                pickle.dump(scaler, f)

            self._model = model
            self._scaler = scaler
            logger.info("Isolation Forest trained on %d samples", len(rows))
            return True
        except Exception as e:
            logger.error("train_model failed: %s", e)
            return False

    def score_run(self, run_data: Dict[str, Any]) -> float:
        """Score via calibrated decision_function. >= 0 normal, < 0 anomaly."""
        if not HAS_SKLEARN or self._model is None:
            return 0.0
        try:
            records_loaded = run_data.get("records_loaded") or 0
            records_failed = run_data.get("records_failed") or 0
            records_ingested = run_data.get("records_ingested") or records_loaded
            X = np.array([[
                records_loaded,
                records_failed,
                records_ingested,
                run_data.get("duration_seconds") or 0,
                run_data.get("hour_of_day") or 9,
                run_data.get("day_of_week") or 0,
                1 if run_data.get("status") == "success" else 0,
                records_failed / max(records_loaded, 1),
            ]], dtype=float)
            if self._scaler is not None:
                X = self._scaler.transform(X)
            return float(self._model.decision_function(X)[0])
        except Exception:
            return 0.0

    def classify_anomaly_type(self, run_data: Dict[str, Any]) -> str:
        """Use classifier to predict specific anomaly type."""
        # Try error message classification first
        err = run_data.get("error_message") or ""
        if err:
            classified = self.classify_error_message(err)
            if classified != "UNKNOWN":
                return classified

        if not HAS_SKLEARN or self._classifier is None or self._label_encoder is None:
            return "ML_ANOMALY"
        try:
            records_loaded = run_data.get("records_loaded") or 0
            records_failed = run_data.get("records_failed") or 0
            X = np.array([[
                records_loaded,
                records_failed,
                run_data.get("duration_seconds") or 0,
                run_data.get("hour_of_day") or 9,
                run_data.get("day_of_week") or 0,
                run_data.get("source_type") or 0,
                1 if run_data.get("status") == "success" else 0,
                records_failed / max(records_loaded, 1),
            ]], dtype=float)
            pred_idx = self._classifier.predict(X)[0]
            label = self._label_encoder.inverse_transform([pred_idx])[0]
            return label if label != "NORMAL" else "ML_ANOMALY"
        except Exception as e:
            logger.warning("classify_anomaly_type failed: %s", e)
            return "ML_ANOMALY"

    # ── Internal checks ────────────────────────────────────────────────────────

    def _run_checks(self, cur, pipeline_name: str) -> Optional[HealingAgentState]:
        latest = self._latest_run(cur, pipeline_name)
        if latest is None:
            return None

        seven_day = self._seven_day_stats(cur, pipeline_name)
        details: Dict[str, Any] = {
            "pipeline_name": pipeline_name,
            "latest_run": dict(latest),
            "db_type": self._detect_db_type(cur, pipeline_name),
        }

        # ── 1. ZERO_LOAD ────────────────────────────────────────────────────
        if (latest.get("records_loaded") or 0) == 0 and latest.get("status") == "success":
            details["records_loaded"] = 0
            return self._make_state(pipeline_name, "ZERO_LOAD", details, str(latest.get("id", "")))

        # ── 2. CONSECUTIVE_FAILURES ─────────────────────────────────────────
        consecutive = self._consecutive_failures(cur, pipeline_name)
        if consecutive >= CONSECUTIVE_FAILURES:
            details["consecutive_failures"] = consecutive
            # Classify from the error message of the latest failure
            err_msg = latest.get("error_message") or ""
            anomaly = self.classify_error_message(err_msg) if err_msg else "CONSECUTIVE_FAILURES"
            return self._make_state(pipeline_name, anomaly, details, str(latest.get("id", "")))

        # ── 3. SCHEMA_DRIFT ─────────────────────────────────────────────────
        schema_drift = self._check_schema_drift(cur, pipeline_name)
        if schema_drift:
            details.update(schema_drift)
            return self._make_state(pipeline_name, "SCHEMA_DRIFT", details, str(latest.get("id", "")))

        # ── 4. ROW_COUNT_DROP ────────────────────────────────────────────────
        avg_loaded = seven_day.get("avg_loaded") or 0
        if avg_loaded > 0:
            latest_loaded = latest.get("records_loaded") or 0
            drop_pct = (avg_loaded - latest_loaded) / avg_loaded
            if drop_pct > ROW_DROP_THRESHOLD:
                details.update({"avg_loaded_7d": avg_loaded, "latest_loaded": latest_loaded, "drop_pct": drop_pct})
                return self._make_state(pipeline_name, "ROW_COUNT_DROP", details, str(latest.get("id", "")))

        # ── 5. NULL_SPIKE ────────────────────────────────────────────────────
        avg_failed  = seven_day.get("avg_failed") or 0
        avg_ingested = seven_day.get("avg_ingested") or 1
        latest_failed = latest.get("records_failed") or 0
        if (avg_failed / avg_ingested < 0.02 and
                latest_failed / max(avg_ingested, 1) > NULL_SPIKE_THRESHOLD):
            details.update({
                "avg_null_rate": avg_failed / avg_ingested,
                "latest_null_rate": latest_failed / avg_ingested,
            })
            return self._make_state(pipeline_name, "NULL_SPIKE", details, str(latest.get("id", "")))

        # ── 6. DUPLICATE_SPIKE ───────────────────────────────────────────────
        dup_info = self._check_duplicate_spike(cur, pipeline_name, seven_day)
        if dup_info:
            details.update(dup_info)
            return self._make_state(pipeline_name, "DUPLICATE_SPIKE", details, str(latest.get("id", "")))

        # ── 7. SLA_BREACH ────────────────────────────────────────────────────
        sla_target = PIPELINE_SLA.get(pipeline_name, 3600)
        latest_dur = latest.get("duration_seconds") or 0
        if latest_dur > sla_target * SLA_BREACH_MULTIPLIER:
            details.update({"sla_target_s": sla_target, "actual_duration_s": latest_dur,
                             "sla_breach_ratio": latest_dur / sla_target})
            return self._make_state(pipeline_name, "SLA_BREACH", details, str(latest.get("id", "")))

        # ── 8. PIPELINE_DELAY (standard delay, pre-SLA) ──────────────────────
        avg_duration = seven_day.get("avg_duration") or 0
        if avg_duration > 0 and latest_dur > DELAY_MULTIPLIER * avg_duration:
            details.update({"avg_duration_s": avg_duration, "latest_duration_s": latest_dur})
            return self._make_state(pipeline_name, "PIPELINE_DELAY", details, str(latest.get("id", "")))

        # ── 9. CDC_LAG (Kafka consumer only) ────────────────────────────────
        if pipeline_name == "kafka_consumer":
            cdc_lag = self._check_cdc_lag(cur, pipeline_name)
            if cdc_lag:
                details.update(cdc_lag)
                return self._make_state(pipeline_name, "CDC_LAG", details, str(latest.get("id", "")))

        # ── 10. INCREMENTAL_SYNC_FAILURE ────────────────────────────────────
        incremental = self._check_incremental_sync(cur, pipeline_name)
        if incremental:
            details.update(incremental)
            return self._make_state(pipeline_name, "INCREMENTAL_SYNC_FAILURE", details, str(latest.get("id", "")))

        # ── 11. CASCADING_FAILURE (downstream impact) ────────────────────────
        cascade = self._check_cascading_failure(cur, pipeline_name)
        if cascade:
            details.update(cascade)
            return self._make_state(pipeline_name, "CASCADING_FAILURE", details, str(latest.get("id", "")))

        # ── 12. ML Isolation Forest check ────────────────────────────────────
        if HAS_SKLEARN and self._model is not None:
            score = self.score_run(dict(latest))
            if score < ANOMALY_SCORE_THRESHOLD:
                run_dict = dict(latest)
                anomaly_type = self.classify_anomaly_type(run_dict)
                proba = self._get_classifier_proba(run_dict)
                details["isolation_forest_score"] = score
                details["ml_confidence"] = round(proba, 4) if proba else None
                return self._make_state(pipeline_name, anomaly_type, details, str(latest.get("id", "")))

        return None  # healthy

    # ── Specialised checks ─────────────────────────────────────────────────────

    def _check_schema_drift(self, cur, pipeline_name: str) -> Optional[Dict]:
        """Detect column additions/removals by comparing error messages for schema-related errors."""
        cur.execute("""
            SELECT error_message FROM pipeline_runs
            WHERE pipeline_name = %s AND status = 'failed'
              AND started_at >= NOW() - INTERVAL '1 day'
            ORDER BY started_at DESC LIMIT 3
        """, (pipeline_name,))
        rows = cur.fetchall()
        drift_keywords = ["column", "schema", "does not exist", "no attribute",
                          "unexpected field", "schema evolution", "schema mismatch",
                          "extra field", "missing field", "type mismatch", "cast failed"]
        for row in rows:
            msg = (row[0] or "").lower()
            for kw in drift_keywords:
                if kw in msg:
                    return {"schema_drift_detected": True, "error_sample": msg[:200], "drift_keyword": kw}
        return None

    def _check_duplicate_spike(self, cur, pipeline_name: str, seven_day: Dict) -> Optional[Dict]:
        """Check if records_failed/records_ingested ratio spiked (duplicates raise failures)."""
        cur.execute("""
            SELECT AVG(CASE WHEN records_ingested > 0
                       THEN records_failed::float / records_ingested ELSE 0 END)
            FROM pipeline_runs
            WHERE pipeline_name = %s
              AND started_at >= NOW() - INTERVAL '1 hour'
              AND status = 'success'
        """, (pipeline_name,))
        row = cur.fetchone()
        recent_fail_rate = float(row[0] or 0)
        avg_fail_rate = (seven_day.get("avg_failed") or 0) / max(seven_day.get("avg_ingested") or 1, 1)
        if recent_fail_rate > avg_fail_rate + DUPLICATE_SPIKE_RATIO:
            return {
                "recent_fail_rate": recent_fail_rate,
                "baseline_fail_rate": avg_fail_rate,
                "spike_delta": recent_fail_rate - avg_fail_rate,
            }
        return None

    def _check_cdc_lag(self, cur, pipeline_name: str) -> Optional[Dict]:
        """Detect CDC lag: time since last successful run > CDC_LAG_SECONDS."""
        cur.execute("""
            SELECT EXTRACT(EPOCH FROM (NOW() - MAX(completed_at))) AS lag_seconds
            FROM pipeline_runs
            WHERE pipeline_name = %s AND status = 'success'
        """, (pipeline_name,))
        row = cur.fetchone()
        lag = float(row[0] or 0)
        if lag > CDC_LAG_SECONDS:
            return {"cdc_lag_seconds": lag, "cdc_lag_threshold": CDC_LAG_SECONDS}
        return None

    def _check_incremental_sync(self, cur, pipeline_name: str) -> Optional[Dict]:
        """Detect incremental sync failure: records_loaded today < records_loaded yesterday's same hour."""
        cur.execute("""
            SELECT
                SUM(CASE WHEN started_at >= CURRENT_DATE THEN records_loaded ELSE 0 END) AS today,
                SUM(CASE WHEN started_at >= CURRENT_DATE - 1 AND started_at < CURRENT_DATE THEN records_loaded ELSE 0 END) AS yesterday
            FROM pipeline_runs
            WHERE pipeline_name = %s AND status = 'success'
              AND started_at >= CURRENT_DATE - 1
        """, (pipeline_name,))
        row = cur.fetchone()
        today, yesterday = float(row[0] or 0), float(row[1] or 0)
        if yesterday > 0 and today == 0:
            return {"today_records": today, "yesterday_records": yesterday,
                    "sync_gap": "No records loaded today vs yesterday"}
        return None

    def _check_cascading_failure(self, cur, pipeline_name: str) -> Optional[Dict]:
        """Detect if multiple pipelines are failing simultaneously (cascading infra issue)."""
        if pipeline_name != "ingest_nyc_taxi":  # Only check once per cycle
            return None
        cur.execute("""
            SELECT pipeline_name, COUNT(*) AS fail_count
            FROM pipeline_runs
            WHERE status = 'failed' AND started_at >= NOW() - INTERVAL '30 minutes'
            GROUP BY pipeline_name
            HAVING COUNT(*) >= 1
        """)
        failing = cur.fetchall()
        if len(failing) >= 3:  # 3+ pipelines failing → cascade
            return {
                "failing_pipelines": [r[0] for r in failing],
                "cascade_count": len(failing),
            }
        return None

    def _detect_db_type(self, cur, pipeline_name: str) -> str:
        """Infer DB type from pipeline name or config (heuristic)."""
        mapping = {
            "ingest_nyc_taxi": "postgresql",
            "ingest_ecommerce": "kafka",
            "dbt_run": "postgresql",
            "kafka_consumer": "kafka",
        }
        return mapping.get(pipeline_name, "postgresql")

    # ── DB query helpers ───────────────────────────────────────────────────────

    def _latest_run(self, cur, pipeline_name: str) -> Optional[Dict]:
        cur.execute("""
            SELECT id, run_id, records_ingested, records_loaded, records_failed,
                   status, error_message, started_at, completed_at, duration_seconds
            FROM pipeline_runs
            WHERE pipeline_name = %s
            ORDER BY started_at DESC LIMIT 1
        """, (pipeline_name,))
        row = cur.fetchone()
        return dict(row) if row else None

    def _seven_day_stats(self, cur, pipeline_name: str) -> Dict[str, float]:
        cur.execute("""
            SELECT AVG(records_loaded)   AS avg_loaded,
                   AVG(records_ingested) AS avg_ingested,
                   AVG(records_failed)   AS avg_failed,
                   AVG(duration_seconds) AS avg_duration,
                   STDDEV(records_loaded) AS std_loaded
            FROM pipeline_runs
            WHERE pipeline_name = %s
              AND started_at >= NOW() - INTERVAL '7 days'
              AND status = 'success'
        """, (pipeline_name,))
        row = cur.fetchone()
        if row:
            return {
                "avg_loaded":   float(row[0] or 0),
                "avg_ingested": float(row[1] or 0),
                "avg_failed":   float(row[2] or 0),
                "avg_duration": float(row[3] or 0),
                "std_loaded":   float(row[4] or 0),
            }
        return {}

    def _consecutive_failures(self, cur, pipeline_name: str) -> int:
        cur.execute("""
            SELECT status FROM pipeline_runs
            WHERE pipeline_name = %s
            ORDER BY started_at DESC LIMIT %s
        """, (pipeline_name, CONSECUTIVE_FAILURES + 2))
        rows = cur.fetchall()
        count = 0
        for row in rows:
            if row[0] == "failed":
                count += 1
            else:
                break
        return count

    def _get_classifier_proba(self, run_dict: Dict) -> Optional[float]:
        if not HAS_SKLEARN or self._classifier is None:
            return None
        try:
            records_loaded = run_dict.get("records_loaded") or 0
            records_failed = run_dict.get("records_failed") or 0
            X = np.array([[
                records_loaded, records_failed,
                run_dict.get("duration_seconds") or 0,
                run_dict.get("hour_of_day") or 9,
                run_dict.get("day_of_week") or 0,
                run_dict.get("source_type") or 0,
                1 if run_dict.get("status") == "success" else 0,
                records_failed / max(records_loaded, 1),
            ]], dtype=float)
            return float(self._classifier.predict_proba(X).max())
        except Exception:
            return None

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _make_state(
        self, pipeline_name: str, anomaly_type: str,
        anomaly_details: Dict[str, Any], run_id: str = "",
    ) -> HealingAgentState:
        return HealingAgentState(
            pipeline_name=pipeline_name,
            run_id=run_id,
            incident_id=None,
            started_at=datetime.utcnow().isoformat(),
            anomaly_type=anomaly_type,
            anomaly_details=anomaly_details,
            lineage_graph=None,
            root_cause=None,
            root_cause_confidence=None,
            fix_code=None,
            fix_language=None,
            sandbox_results=None,
            tests_passed=None,
            tests_failed=None,
            confidence_score=None,
            approval_status="pending",
            approval_email=None,
            approval_token=None,
            deployed=None,
            deployment_result=None,
            error=None,
            reasoning_steps=[f"MonitoringAgent detected {anomaly_type}"],
        )

    def _load_model(self):
        try:
            if MODEL_PATH.exists():
                with open(MODEL_PATH, "rb") as f:
                    self._model = pickle.load(f)
            if SCALER_PATH.exists():
                with open(SCALER_PATH, "rb") as f:
                    self._scaler = pickle.load(f)
            if CLASSIFIER_PATH.exists():
                with open(CLASSIFIER_PATH, "rb") as f:
                    self._classifier = pickle.load(f)
            if LABEL_ENCODER_PATH.exists():
                with open(LABEL_ENCODER_PATH, "rb") as f:
                    self._label_encoder = pickle.load(f)
        except Exception as e:
            logger.warning("Could not load ML model: %s", e)
