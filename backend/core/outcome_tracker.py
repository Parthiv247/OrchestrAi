"""
OutcomeTracker — Records healing outcomes and computes strategy success rates.

Called from the approval API when approve/reject is triggered.
Stores structured records in the healing_outcomes PostgreSQL table so that
MTTR and strategy effectiveness can be computed and charted over time.
"""
import hashlib
import logging
import os
from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "orchestrai"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}


def _get_conn():
    """Return a raw psycopg2 connection."""
    return psycopg2.connect(**DB_CONFIG, connect_timeout=10)


class OutcomeTracker:
    """Records healing outcomes and computes strategy/MTTR learning statistics."""

    # ── Write path ──────────────────────────────────────────────────────────────

    def record_outcome(
        self,
        incident_id: str,
        pipeline_name: str,
        anomaly_type: str,
        healing_strategy: str,
        outcome: str,
        fix_code: str = "",
        confidence_score: float = 0.0,
        detection_at: datetime | None = None,
        approved_by: str | None = None,
    ) -> bool:
        """
        Record a healing outcome (called on approve/reject).

        Parameters
        ----------
        incident_id       : unique incident UUID
        pipeline_name     : name of the affected pipeline
        anomaly_type      : e.g. 'ZERO_LOAD', 'SCHEMA_DRIFT'
        healing_strategy  : e.g. 'restart_pipeline', 'schema_evolution'
        outcome           : one of 'approved', 'rejected', 'auto_healed'
        fix_code          : the fix code that was generated (used to compute hash)
        confidence_score  : agent's confidence in the fix (0–1)
        detection_at      : when the anomaly was first detected (for MTTR)
        approved_by       : email/username of approver, if applicable
        """
        mttr = None
        if detection_at:
            mttr = (datetime.utcnow() - detection_at).total_seconds()

        fix_hash = hashlib.sha256(fix_code.encode()).hexdigest()[:16] if fix_code else None

        try:
            conn = _get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO healing_outcomes
                        (incident_id, pipeline_name, anomaly_type, healing_strategy,
                         fix_code_hash, outcome, mttr_seconds, confidence_score,
                         approved_by, detection_at, resolved_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    """,
                    (
                        incident_id,
                        pipeline_name,
                        anomaly_type,
                        healing_strategy,
                        fix_hash,
                        outcome,
                        mttr,
                        confidence_score,
                        approved_by,
                        detection_at,
                    ),
                )
                conn.commit()
            conn.close()
            logger.info(
                "OutcomeTracker: recorded %s for incident %s (MTTR=%.1fs)",
                outcome,
                incident_id[:8],
                mttr or 0,
            )
            return True
        except Exception as e:
            logger.error("OutcomeTracker.record_outcome failed: %s", e)
            return False

    # ── Read / analytics path ──────────────────────────────────────────────────

    def get_strategy_success_rates(self) -> dict[str, Any]:
        """
        Returns per-anomaly-type strategy success rates.

        Used by orchestrator to pick the best strategy.

        Return format::

            {
              'ZERO_LOAD': {
                'best_strategy': 'restart_pipeline',
                'success_rate': 0.85,
                'count': 12,
                'avg_mttr_seconds': 92.4,
              },
              ...
            }
        """
        sql = """
            SELECT
                anomaly_type,
                healing_strategy,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE outcome = 'approved' OR outcome = 'auto_healed') AS successes,
                AVG(mttr_seconds) FILTER (WHERE mttr_seconds IS NOT NULL) AS avg_mttr
            FROM healing_outcomes
            GROUP BY anomaly_type, healing_strategy
            ORDER BY anomaly_type, successes DESC
        """
        try:
            conn = _get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchall()
            conn.close()
        except Exception as e:
            logger.error("get_strategy_success_rates failed: %s", e)
            return {}

        # Aggregate: per anomaly_type, pick the best strategy
        result: dict[str, Any] = {}
        for row in rows:
            at = row["anomaly_type"]
            total = row["total"] or 1
            rate = round((row["successes"] or 0) / total, 4)
            entry = {
                "strategy": row["healing_strategy"],
                "success_rate": rate,
                "count": row["total"],
                "avg_mttr_seconds": round(float(row["avg_mttr"] or 0), 2),
            }
            if at not in result:
                result[at] = {
                    "best_strategy": row["healing_strategy"],
                    "success_rate": rate,
                    "count": row["total"],
                    "avg_mttr_seconds": entry["avg_mttr_seconds"],
                    "strategies": [entry],
                }
            else:
                result[at]["strategies"].append(entry)
                # Keep best_strategy as the one with highest success_rate
                if rate > result[at]["success_rate"]:
                    result[at]["best_strategy"] = row["healing_strategy"]
                    result[at]["success_rate"] = rate

        return result

    def get_mttr_trend(self, days: int = 30) -> list[dict]:
        """
        Returns daily average MTTR for the last N days.

        Return format::

            [
              {'date': '2025-01-01', 'avg_mttr_seconds': 45.2, 'incident_count': 3},
              ...
            ]
        """
        sql = """
            SELECT
                DATE(resolved_at) AS day,
                AVG(mttr_seconds)  AS avg_mttr,
                COUNT(*)           AS incident_count
            FROM healing_outcomes
            WHERE resolved_at >= NOW() - INTERVAL '%s days'
              AND mttr_seconds IS NOT NULL
            GROUP BY day
            ORDER BY day ASC
        """
        try:
            conn = _get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (days,))
                rows = cur.fetchall()
            conn.close()
        except Exception as e:
            logger.error("get_mttr_trend failed: %s", e)
            return []

        return [
            {
                "date": str(row["day"]),
                "avg_mttr_seconds": round(float(row["avg_mttr"] or 0), 2),
                "incident_count": row["incident_count"],
            }
            for row in rows
        ]

    def get_learning_stats(self) -> dict[str, Any]:
        """
        Full stats for the /api/learning/stats endpoint.

        Returns a dict with:
          - total_outcomes        : int
          - avg_mttr              : float (seconds)
          - success_rate          : float (0–1)
          - mttr_trend            : list of daily MTTR dicts (last 30 days)
          - strategy_performance  : dict of anomaly_type → strategy stats
          - top_anomaly_types     : list of (anomaly_type, count) tuples
          - weekly_improvement_pct: float — MTTR reduction vs. 4 weeks ago
        """
        aggregates_sql = """
            SELECT
                COUNT(*)                                                              AS total_outcomes,
                AVG(mttr_seconds) FILTER (WHERE mttr_seconds IS NOT NULL)            AS avg_mttr,
                COUNT(*) FILTER (WHERE outcome IN ('approved','auto_healed'))::FLOAT
                    / NULLIF(COUNT(*), 0)                                             AS success_rate
            FROM healing_outcomes
        """
        top_anomaly_sql = """
            SELECT anomaly_type, COUNT(*) AS cnt
            FROM healing_outcomes
            GROUP BY anomaly_type
            ORDER BY cnt DESC
            LIMIT 10
        """
        weekly_sql = """
            SELECT
                AVG(mttr_seconds) FILTER (
                    WHERE resolved_at >= NOW() - INTERVAL '7 days'
                      AND mttr_seconds IS NOT NULL
                ) AS this_week,
                AVG(mttr_seconds) FILTER (
                    WHERE resolved_at >= NOW() - INTERVAL '28 days'
                      AND resolved_at <  NOW() - INTERVAL '21 days'
                      AND mttr_seconds IS NOT NULL
                ) AS four_weeks_ago
            FROM healing_outcomes
        """

        total_outcomes = 0
        avg_mttr = 0.0
        success_rate = 0.0
        top_anomaly_types: list = []
        weekly_improvement_pct = 0.0

        try:
            conn = _get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(aggregates_sql)
                agg = cur.fetchone() or {}
                total_outcomes = int(agg.get("total_outcomes") or 0)
                avg_mttr = round(float(agg.get("avg_mttr") or 0), 2)
                success_rate = round(float(agg.get("success_rate") or 0), 4)

                cur.execute(top_anomaly_sql)
                top_anomaly_types = [
                    {"anomaly_type": row["anomaly_type"], "count": row["cnt"]}
                    for row in cur.fetchall()
                ]

                cur.execute(weekly_sql)
                wrow = cur.fetchone() or {}
                this_week = float(wrow.get("this_week") or 0)
                four_weeks_ago = float(wrow.get("four_weeks_ago") or 0)
                if four_weeks_ago > 0:
                    weekly_improvement_pct = round(
                        (four_weeks_ago - this_week) / four_weeks_ago * 100, 1
                    )

            conn.close()
        except Exception as e:
            logger.error("get_learning_stats aggregates failed: %s", e)

        mttr_trend = self.get_mttr_trend(days=30)
        strategy_performance = self.get_strategy_success_rates()

        return {
            "total_outcomes": total_outcomes,
            "avg_mttr": avg_mttr,
            "success_rate": success_rate,
            "mttr_trend": mttr_trend,
            "strategy_performance": strategy_performance,
            "top_anomaly_types": top_anomaly_types,
            "weekly_improvement_pct": weekly_improvement_pct,
        }
