"""
MonitoringAgent — Watches all 4 pipelines via rule-based checks + Isolation Forest ML.

Rule checks run on pipeline_runs table; ML model trains on pipeline_metrics.
Detects: ROW_COUNT_DROP, NULL_SPIKE, PIPELINE_DELAY, ZERO_LOAD, CONSECUTIVE_FAILURES.
"""
import os
import pickle
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import psycopg2
import psycopg2.extras

try:
    import numpy as np
    from sklearn.ensemble import IsolationForest
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from .state import HealingAgentState

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "orchestrai"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}

MODEL_PATH = Path(__file__).parent.parent.parent.parent / "ml" / "isolation_forest.pkl"
SCALER_PATH = Path(__file__).parent.parent.parent.parent / "ml" / "scaler.pkl"
CLASSIFIER_PATH    = Path(__file__).parent.parent.parent.parent / "ml" / "anomaly_classifier.pkl"
LABEL_ENCODER_PATH = Path(__file__).parent.parent.parent.parent / "ml" / "label_encoder.pkl"

PIPELINE_NAMES = ["ingest_nyc_taxi", "ingest_ecommerce", "dbt_run", "kafka_consumer"]

# Thresholds
ROW_DROP_THRESHOLD = 0.20        # >20% drop vs 7-day avg → flag
NULL_SPIKE_THRESHOLD = 0.10      # >10% nulls when avg <2% → flag
DELAY_MULTIPLIER = 2.0           # duration > 2x avg → flag
# IsolationForest.decision_function is calibrated by `contamination`: >= 0 is
# normal, < 0 is an outlier (this is exactly what .predict() uses). We flag below
# this. (The old code compared raw score_samples — which is ~-0.4 even for normal
# points — against -0.1, so it flagged essentially every run as an anomaly.)
ANOMALY_SCORE_THRESHOLD = 0.0
CONSECUTIVE_FAILURES = 2         # same pipeline failed N times in a row → flag


class MonitoringAgent:
    """Continuously watches all 4 pipelines and detects anomalies."""

    def __init__(self):
        self._model: Optional[Any] = None
        self._scaler: Optional[Any] = None
        self._classifier: Optional[Any] = None
        self._label_encoder: Optional[Any] = None
        self._load_model()

    # ── Public API ─────────────────────────────────────────────────────────────

    def check_pipeline(self, pipeline_name: str) -> Optional[HealingAgentState]:
        """Run all checks for one pipeline. Returns HealingAgentState if anomaly found, else None."""
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
        """Check every pipeline; return list of anomalous states (empty = all healthy)."""
        anomalies = []
        for name in PIPELINE_NAMES:
            state = self.check_pipeline(name)
            if state is not None:
                anomalies.append(state)
        return anomalies

    def train_model(self) -> bool:
        """Train Isolation Forest on last 30 days of pipeline_metrics, save to disk."""
        if not HAS_SKLEARN:
            logger.warning("scikit-learn not installed — skipping model training")
            return False
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT records_loaded, records_failed,
                           EXTRACT(EPOCH FROM (completed_at - started_at)) AS duration,
                           CASE WHEN status = 'success' THEN 1 ELSE 0 END AS success_flag
                    FROM pipeline_runs
                    WHERE started_at >= NOW() - INTERVAL '30 days'
                      AND completed_at IS NOT NULL
                    ORDER BY started_at
                """)
                rows = cur.fetchall()
            conn.close()

            if len(rows) < 5:
                logger.warning("Not enough data to train Isolation Forest (%d rows)", len(rows))
                return False

            X = np.array([[r[0] or 0, r[1] or 0, r[2] or 0, r[3]] for r in rows], dtype=float)

            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            model = IsolationForest(contamination=0.1, random_state=42, n_estimators=100)
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
        """Score a single run via the calibrated decision_function.
        >= 0 → normal, < 0 → anomaly (lower = more anomalous)."""
        if not HAS_SKLEARN or self._model is None:
            return 0.0
        try:
            X = np.array([[
                run_data.get("records_loaded", 0) or 0,
                run_data.get("records_failed", 0) or 0,
                run_data.get("duration_seconds", 0) or 0,
                1 if run_data.get("status") == "success" else 0,
            ]], dtype=float)
            if self._scaler is not None:
                X = self._scaler.transform(X)
            return float(self._model.decision_function(X)[0])
        except Exception:
            return 0.0

    def classify_anomaly_type(self, run_data: Dict[str, Any]) -> str:
        """Use RandomForest classifier to predict specific anomaly type.
        Falls back to "ML_ANOMALY" if classifier not loaded."""
        if not HAS_SKLEARN or self._classifier is None or self._label_encoder is None:
            return "ML_ANOMALY"
        try:
            import numpy as np
            X = np.array([[
                run_data.get("records_loaded", 0) or 0,
                run_data.get("records_failed", 0) or 0,
                run_data.get("duration_seconds", 0) or 0,
                run_data.get("hour_of_day", 9),
                run_data.get("day_of_week", 0),
                run_data.get("source_type", 0),
                1 if run_data.get("status") == "success" else 0,
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

        seven_day_stats = self._seven_day_stats(cur, pipeline_name)
        details: Dict[str, Any] = {"pipeline_name": pipeline_name, "latest_run": dict(latest)}

        # ZERO_LOAD — immediate flag
        if (latest.get("records_loaded") or 0) == 0 and latest.get("status") == "success":
            details["records_loaded"] = 0
            return self._make_state(pipeline_name, "ZERO_LOAD", details, str(latest.get("id", "")))

        # CONSECUTIVE_FAILURES
        consecutive = self._consecutive_failures(cur, pipeline_name)
        if consecutive >= CONSECUTIVE_FAILURES:
            details["consecutive_failures"] = consecutive
            return self._make_state(pipeline_name, "CONSECUTIVE_FAILURES", details, str(latest.get("id", "")))

        # ROW_COUNT_DROP
        avg_loaded = seven_day_stats.get("avg_loaded", 0) or 0
        if avg_loaded > 0:
            latest_loaded = latest.get("records_loaded") or 0
            drop_pct = (avg_loaded - latest_loaded) / avg_loaded
            if drop_pct > ROW_DROP_THRESHOLD:
                details.update({"avg_loaded_7d": avg_loaded, "latest_loaded": latest_loaded, "drop_pct": drop_pct})
                return self._make_state(pipeline_name, "ROW_COUNT_DROP", details, str(latest.get("id", "")))

        # NULL_SPIKE — check records_failed as proxy for nulls
        avg_failed = seven_day_stats.get("avg_failed", 0) or 0
        latest_failed = latest.get("records_failed") or 0
        avg_ingested = seven_day_stats.get("avg_ingested", 1) or 1
        if avg_failed / avg_ingested < 0.02 and latest_failed / max(avg_ingested, 1) > NULL_SPIKE_THRESHOLD:
            details.update({"avg_null_rate": avg_failed / avg_ingested, "latest_null_rate": latest_failed / avg_ingested})
            return self._make_state(pipeline_name, "NULL_SPIKE", details, str(latest.get("id", "")))

        # PIPELINE_DELAY
        avg_duration = seven_day_stats.get("avg_duration", 0) or 0
        latest_duration = latest.get("duration_seconds") or 0
        if avg_duration > 0 and latest_duration > DELAY_MULTIPLIER * avg_duration:
            details.update({"avg_duration_s": avg_duration, "latest_duration_s": latest_duration})
            return self._make_state(pipeline_name, "PIPELINE_DELAY", details, str(latest.get("id", "")))

        # ML Isolation Forest check
        if HAS_SKLEARN and self._model is not None:
            score = self.score_run(dict(latest))
            if score < ANOMALY_SCORE_THRESHOLD:
                run_dict = dict(latest)
                anomaly_type = self.classify_anomaly_type(run_dict)
                proba = None
                if self._classifier is not None:
                    try:
                        import numpy as np
                        X = np.array([[
                            run_dict.get("records_loaded", 0) or 0,
                            run_dict.get("records_failed", 0) or 0,
                            run_dict.get("duration_seconds", 0) or 0,
                            run_dict.get("hour_of_day", 9),
                            run_dict.get("day_of_week", 0),
                            run_dict.get("source_type", 0),
                            1 if run_dict.get("status") == "success" else 0,
                        ]], dtype=float)
                        proba = float(self._classifier.predict_proba(X).max())
                    except Exception:
                        pass
                details["isolation_forest_score"] = score
                details["ml_confidence"] = round(proba, 4) if proba is not None else None
                return self._make_state(pipeline_name, anomaly_type, details, str(latest.get("id", "")))

        return None  # healthy

    def _latest_run(self, cur, pipeline_name: str) -> Optional[Dict]:
        cur.execute("""
            SELECT id, run_id, records_ingested, records_loaded, records_failed,
                   status, error_message, started_at, completed_at, duration_seconds
            FROM pipeline_runs
            WHERE pipeline_name = %s
            ORDER BY started_at DESC
            LIMIT 1
        """, (pipeline_name,))
        row = cur.fetchone()
        return dict(row) if row else None

    def _seven_day_stats(self, cur, pipeline_name: str) -> Dict[str, float]:
        cur.execute("""
            SELECT AVG(records_loaded)   AS avg_loaded,
                   AVG(records_ingested) AS avg_ingested,
                   AVG(records_failed)   AS avg_failed,
                   AVG(duration_seconds) AS avg_duration
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
            }
        return {}

    def _consecutive_failures(self, cur, pipeline_name: str) -> int:
        cur.execute("""
            SELECT status FROM pipeline_runs
            WHERE pipeline_name = %s
            ORDER BY started_at DESC
            LIMIT %s
        """, (pipeline_name, CONSECUTIVE_FAILURES + 2))
        rows = cur.fetchall()
        count = 0
        for row in rows:
            if row[0] == "failed":
                count += 1
            else:
                break
        return count

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _make_state(
        self,
        pipeline_name: str,
        anomaly_type: str,
        anomaly_details: Dict[str, Any],
        run_id: str = "",
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
                logger.info("Anomaly classifier loaded from %s", CLASSIFIER_PATH)
            if LABEL_ENCODER_PATH.exists():
                with open(LABEL_ENCODER_PATH, "rb") as f:
                    self._label_encoder = pickle.load(f)
                logger.info("Label encoder loaded from %s", LABEL_ENCODER_PATH)
        except Exception as e:
            logger.warning("Could not load ML model: %s", e)
