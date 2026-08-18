"""
FastAPI routes for Learning Agent statistics.

GET /api/learning/stats               — combined ChromaDB RAG + outcome tracking stats
GET /api/learning/mttr-trend          — daily MTTR for the last N days
GET /api/learning/strategy-performance — per-anomaly-type strategy success rates
"""
import logging

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/learning", tags=["Learning"])


@router.get("/stats")
def get_learning_stats():
    """
    Combined stats: ChromaDB RAG stats + outcome tracking + MTTR trend.

    Merges data from:
      - OutcomeTracker (PostgreSQL healing_outcomes table)
      - LearningAgent  (ChromaDB pipeline_fixes / nl_queries collections)
    """
    outcome_stats: dict = {
        "total_outcomes": 0,
        "avg_mttr": 0.0,
        "success_rate": 0.0,
        "mttr_trend": [],
        "strategy_performance": {},
        "top_anomaly_types": [],
        "weekly_improvement_pct": 0.0,
    }
    rag_stats: dict = {
        "total_fixes_stored": 0,
        "total_queries_stored": 0,
    }

    try:
        from ...core.outcome_tracker import OutcomeTracker
        outcome_stats = OutcomeTracker().get_learning_stats()
    except Exception as e:
        logger.warning("OutcomeTracker.get_learning_stats failed: %s", e)

    try:
        from ...agents.learning.learning_agent import LearningAgent
        rag_stats = LearningAgent().get_stats()
    except Exception as e:
        logger.warning("LearningAgent.get_stats failed: %s", e)

    return {
        **outcome_stats,
        "rag_fixes_stored": rag_stats.get("total_fixes_stored", 0),
        "rag_queries_stored": rag_stats.get("total_queries_stored", 0),
    }


@router.get("/mttr-trend")
def get_mttr_trend(days: int = Query(30, ge=1, le=365)):
    """
    Daily average MTTR for the last N days (default 30).

    Returns a list of::

        {'date': 'YYYY-MM-DD', 'avg_mttr_seconds': float, 'incident_count': int}
    """
    try:
        from ...core.outcome_tracker import OutcomeTracker
        return OutcomeTracker().get_mttr_trend(days=days)
    except Exception as e:
        logger.error("get_mttr_trend failed: %s", e)
        return []


@router.get("/strategy-performance")
def get_strategy_performance():
    """
    Per-anomaly-type strategy success rates.

    Returns a dict keyed by anomaly_type, each value containing::

        {
          'best_strategy': str,
          'success_rate': float,
          'count': int,
          'avg_mttr_seconds': float,
          'strategies': [{'strategy': str, 'success_rate': float, 'count': int, 'avg_mttr_seconds': float}, ...]
        }
    """
    try:
        from ...core.outcome_tracker import OutcomeTracker
        return OutcomeTracker().get_strategy_success_rates()
    except Exception as e:
        logger.error("get_strategy_performance failed: %s", e)
        return {}
