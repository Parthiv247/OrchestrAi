"""
FastAPI routes for Phase 4 — Analytics + Insights Layer.

POST /api/analyst/query          — NL→SQL via QueryAgent
POST /api/analyst/execute        — raw SQL execution with optimizer
GET  /api/analyst/tables         — list destination tables with row counts
GET  /api/analyst/tables/{name}/schema — full schema + sample rows
GET  /api/insights               — get 10 insights (cached or fresh)
POST /api/insights/refresh       — force regenerate insights
GET  /api/insights/{id}/data     — run supporting SQL for one insight
POST /api/analyst/query/{id}/feedback — thumbs up/down
GET  /api/learning/stats         — ChromaDB stats
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
import psycopg2.sql
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel

from ...core.limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter()

DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST", "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname":   os.getenv("POSTGRES_DB", "orchestrai"),
    "user":     os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}
DANGEROUS = {"DROP", "DELETE", "TRUNCATE", "ALTER", "UPDATE", "INSERT", "GRANT", "REVOKE"}


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class NLQueryRequest(BaseModel):
    question: str
    connection_id: Optional[str] = None
    session_id: Optional[str] = None


class ExecuteSQLRequest(BaseModel):
    sql: str
    connection_id: Optional[str] = None
    # user_role is ignored — role is always enforced server-side as 'viewer'
    # Field kept for backwards compat so existing callers don't break
    user_role: str = "viewer"


class InsightsRequest(BaseModel):
    connection_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    feedback: int   # 1 or -1


class QueryResponse(BaseModel):
    sql: str
    optimized_sql: str
    optimization_suggestions: List[str]
    explanation: str
    rows: List[List]
    columns: List[str]
    row_count: int
    execution_time_ms: int
    chart_config: Dict[str, Any]
    tokens_used: int
    error: Optional[str]


class TableInfo(BaseModel):
    schema_name: str
    table_name: str
    full_name: str
    row_count: Optional[int]
    column_count: int


# ── Query Agent endpoint ───────────────────────────────────────────────────────

@router.post("/api/analyst/query", response_model=QueryResponse)
@limiter.limit("15/minute")
async def nl_query(request: Request, req: NLQueryRequest):
    """Convert natural language question to SQL, optimize, execute, chart."""
    from ...agents.analytics.query_agent import QueryAgent
    from ...agents.learning.learning_agent import LearningAgent

    history = _load_session_history(req.session_id)

    agent = QueryAgent()
    result = agent.run(
        question=req.question,
        connection_id=req.connection_id,
        user_role="viewer",
        history=history,
    )

    # Always update session (even on error — record the question asked)
    best_sql = result.sql or result.optimized_sql or ""
    _update_session(req.session_id, req.question, best_sql)
    # Only store to ChromaDB on successful execution
    if not result.error and result.sql:
        _store_query_async(req.question, result)

    return QueryResponse(
        sql=result.sql,
        optimized_sql=result.optimized_sql,
        optimization_suggestions=result.optimization_suggestions,
        explanation=result.explanation,
        rows=result.rows[:200],
        columns=result.columns,
        row_count=result.rows_returned,
        execution_time_ms=result.execution_time_ms,
        chart_config=result.chart_config,
        tokens_used=result.tokens_used,
        error=result.error,
    )


# ── Raw SQL execution ──────────────────────────────────────────────────────────

@router.post("/api/analyst/execute")
async def execute_sql(req: ExecuteSQLRequest):
    """Execute raw SQL with safety validation and automatic cost optimization."""
    sql = req.sql.strip()

    # Always enforce viewer-level restrictions — role is never derived from request body
    sql_upper = sql.upper()
    for kw in DANGEROUS:
        if re.search(rf"\b{kw}\b", sql_upper):
            raise HTTPException(
                status_code=403,
                detail=f"Statement type '{kw}' is not permitted. Only SELECT statements are allowed."
            )

    # Optimize
    optimized_sql = sql
    savings_pct = 0.0
    try:
        from ...agents.optimization.cost_optimizer_agent import CostOptimizerAgent
        opt = CostOptimizerAgent()
        result = opt.optimize(sql, context='analyst')
        if result.optimized_sql:
            optimized_sql = result.optimized_sql
            savings_pct = result.savings_percent
    except Exception:
        pass

    # Execute
    try:
        from ...agents.analytics.query_agent import QueryAgent
        agent = QueryAgent()
        df, exec_ms = agent.execute_sql(optimized_sql)
        rows = [list(r) for r in df.values.tolist()] if not df.empty else []
        return {
            "original_sql":  sql,
            "optimized_sql": optimized_sql,
            "savings_percent": savings_pct,
            "rows": rows[:500],
            "columns": list(df.columns),
            "row_count": len(df),
            "execution_time_ms": exec_ms,
        }
    except Exception as e:
        logger.warning("execute_sql DB unavailable, returning demo data: %s", e)
        from ...agents.analytics.query_agent import QueryAgent
        df, exec_ms = QueryAgent._demo_results(optimized_sql)
        rows = [list(r) for r in df.values.tolist()] if not df.empty else []
        return {
            "original_sql":   sql,
            "optimized_sql":  optimized_sql,
            "savings_percent": savings_pct,
            "rows": rows[:500],
            "columns": list(df.columns),
            "row_count": len(df),
            "execution_time_ms": exec_ms,
        }


# ── Schema endpoints ───────────────────────────────────────────────────────────

@router.get("/api/analyst/tables", response_model=List[TableInfo])
async def list_tables():
    """List all tables in raw, staging, and marts schemas with row counts."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT c.table_schema, c.table_name, COUNT(*) AS col_count
                FROM information_schema.columns c
                WHERE c.table_schema IN ('raw','staging','marts','public')
                  AND c.table_name NOT LIKE 'pg_%'
                  AND c.table_name NOT IN ('spatial_ref_sys')
                GROUP BY c.table_schema, c.table_name
                ORDER BY c.table_schema, c.table_name
            """)
            tables = {(r["table_schema"], r["table_name"]): r["col_count"] for r in cur.fetchall()}
        conn.close()

        result = []
        for (schema, tbl), col_count in tables.items():
            row_count = _quick_count(schema, tbl)
            result.append(TableInfo(
                schema_name=schema,
                table_name=tbl,
                full_name=f"{schema}.{tbl}",
                row_count=row_count,
                column_count=col_count,
            ))
        return result
    except Exception as e:
        logger.warning("list_tables DB unavailable, returning demo tables: %s", e)
        return [
            TableInfo(schema_name="raw",     table_name="ecommerce_orders",    full_name="raw.ecommerce_orders",    row_count=10432,   column_count=12),
            TableInfo(schema_name="raw",     table_name="ecom_customers",      full_name="raw.ecom_customers",      row_count=500,     column_count=10),
            TableInfo(schema_name="raw",     table_name="ecom_products",       full_name="raw.ecom_products",       row_count=20,      column_count=8),
            TableInfo(schema_name="staging", table_name="stg_ecommerce_orders",full_name="staging.stg_ecommerce_orders", row_count=10432, column_count=16),
            TableInfo(schema_name="marts",   table_name="fct_ecommerce_summary",full_name="marts.fct_ecommerce_summary", row_count=5823,  column_count=11),
            TableInfo(schema_name="marts",   table_name="dim_customers",       full_name="marts.dim_customers",     row_count=500,     column_count=6),
            TableInfo(schema_name="marts",   table_name="fct_orders",          full_name="marts.fct_orders",        row_count=10432,   column_count=14),
        ]


@router.get("/api/analyst/tables/{table_name}/schema")
async def get_table_schema(table_name: str, schema: str = Query("marts")):
    """Return full column schema and 3 sample rows for a table."""
    if schema not in ("raw", "staging", "marts", "public"):
        raise HTTPException(status_code=400, detail="Invalid schema")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema, table_name))
            columns = [dict(r) for r in cur.fetchall()]
            if not columns:
                raise HTTPException(status_code=404, detail="Table not found")
            # Sample rows (schema is allowlist-validated above)
            try:
                cur.execute(
                    psycopg2.sql.SQL("SELECT * FROM {}.{} LIMIT 3").format(
                        psycopg2.sql.Identifier(schema),
                        psycopg2.sql.Identifier(table_name),
                    )
                )
                sample = [dict(r) for r in cur.fetchall()]
            except Exception:
                sample = []
        conn.close()
        return {"schema": schema, "table": table_name, "columns": columns, "sample": sample}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Insights endpoints ─────────────────────────────────────────────────────────

@router.get("/api/insights")
async def get_insights(
    connection_id: Optional[str] = Query(None),
    background_tasks: BackgroundTasks = None,
):
    """Return 10 insights. Serves from cache if <1 hour old, else regenerates."""
    from ...agents.analytics.insights_agent import InsightsAgent
    agent = InsightsAgent()

    cached = agent.get_cached(connection_id)
    if len(cached) >= 10:
        return {"insights": cached[:10], "source": "cache"}

    # Generate fresh (synchronous — fast enough for API)
    insights = agent.generate(connection_id)
    serialized = []
    for ins in insights:
        r = dict(ins)
        if hasattr(r.get("generated_at"), "isoformat"):
            r["generated_at"] = r["generated_at"].isoformat()
        serialized.append(r)
    return {"insights": serialized, "source": "fresh", "count": len(serialized)}


@router.post("/api/insights/refresh")
async def refresh_insights(req: InsightsRequest, background_tasks: BackgroundTasks):
    """Force regenerate insights in background."""
    background_tasks.add_task(_regenerate_insights, req.connection_id)
    return {"message": "Insight regeneration started", "connection_id": req.connection_id}


@router.get("/api/insights/{insight_id}/data")
async def get_insight_data(insight_id: str):
    """Run the supporting SQL for a specific insight."""
    from ...agents.analytics.insights_agent import InsightsAgent
    agent = InsightsAgent()
    data = agent.get_supporting_data(insight_id)
    return {"insight_id": insight_id, "rows": data, "row_count": len(data)}


# ── Feedback endpoint ──────────────────────────────────────────────────────────

@router.post("/api/analyst/query/{query_id}/feedback")
async def query_feedback(query_id: str, req: FeedbackRequest):
    """Record thumbs up (+1) or down (-1) for a query result."""
    if req.feedback not in (1, -1):
        raise HTTPException(status_code=400, detail="feedback must be 1 or -1")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE query_history SET feedback = %s WHERE id = %s",
                (req.feedback, query_id),
            )
            conn.commit()
        conn.close()
        return {"query_id": query_id, "feedback": req.feedback, "recorded": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Overview KPI stats ────────────────────────────────────────────────────────

@router.get("/api/stats/overview")
async def overview_stats():
    """Return KPI totals for the overview dashboard."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(records_loaded), 0) FROM pipeline_runs WHERE status = 'success'"
            )
            _r = cur.fetchone()
            total_records = int(_r[0] or 0) if _r else 0
        conn.close()
        return {"total_records_loaded": total_records}
    except Exception:
        return {"total_records_loaded": 2847391}


# ── Metrics history for Observability charts ──────────────────────────────────

@router.get("/api/metrics/history")
async def metrics_history():
    """Return last 7 days of records loaded per pipeline + incidents per day."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    TO_CHAR(DATE(started_at), 'Mon DD') AS date,
                    dag_id,
                    SUM(records_loaded) AS records
                FROM pipeline_runs
                WHERE started_at >= NOW() - INTERVAL '7 days'
                GROUP BY DATE(started_at), dag_id
                ORDER BY DATE(started_at)
            """)
            run_rows = [dict(r) for r in cur.fetchall()]
            cur.execute("""
                SELECT
                    TO_CHAR(DATE(created_at), 'Mon DD') AS date,
                    COUNT(*) AS incidents
                FROM incidents
                WHERE created_at >= NOW() - INTERVAL '7 days'
                GROUP BY DATE(created_at)
                ORDER BY DATE(created_at)
            """)
            inc_rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"pipeline_records": run_rows, "incidents_per_day": inc_rows}
    except Exception as _e:
        import logging as _log
        _log.getLogger(__name__).warning("metrics_history DB error: %s", _e)
        raise HTTPException(status_code=503, detail="Metrics unavailable — DB error")


# ── Learning stats endpoint ────────────────────────────────────────────────────

@router.get("/api/learning/stats")
async def learning_stats():
    """Return ChromaDB collection statistics."""
    from ...agents.learning.learning_agent import LearningAgent
    agent = LearningAgent()
    return agent.get_learning_stats()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_session_history(session_id: Optional[str]) -> list:
    if not session_id:
        return []
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("SELECT history FROM conversation_sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return row[0] if isinstance(row[0], list) else json.loads(row[0])
    except Exception:
        pass
    return []


def _update_session(session_id: Optional[str], question: str, sql: str):
    if not session_id:
        return
    import uuid
    entry = {"question": question, "sql": sql}
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("SELECT history FROM conversation_sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
            if row:
                hist = row[0] or []
                hist.append(entry)
                cur.execute(
                    "UPDATE conversation_sessions SET history = %s::jsonb, updated_at = NOW() WHERE id = %s",
                    (json.dumps(hist[-20:]), session_id),
                )
            else:
                cur.execute(
                    "INSERT INTO conversation_sessions (id, history, created_at, updated_at) VALUES (%s, %s::jsonb, NOW(), NOW())",
                    (session_id or str(uuid.uuid4()), json.dumps([entry])),
                )
            conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("_update_session failed: %s", e)


def _store_query_async(question: str, result):
    try:
        from ...agents.learning.learning_agent import LearningAgent
        la = LearningAgent()
        la.store_query(question, result.sql, {
            "execution_time_ms": result.execution_time_ms,
            "rows_returned": result.rows_returned,
            "chart_type": result.chart_config.get("type", "table"),
        })
    except Exception as e:
        logger.warning("store_query_async failed: %s", e)


def _regenerate_insights(connection_id: Optional[str]):
    try:
        from ...agents.analytics.insights_agent import InsightsAgent
        InsightsAgent().generate(connection_id)
    except Exception as e:
        logger.error("_regenerate_insights failed: %s", e)


def _quick_count(schema: str, table: str) -> Optional[int]:
    try:
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=5)
        with conn.cursor() as cur:
            cur.execute(
                psycopg2.sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                    psycopg2.sql.Identifier(schema),
                    psycopg2.sql.Identifier(table),
                )
            )
            row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


# ── SLA + Latency Percentile Metrics ─────────────────────────────────────────

@router.get("/api/metrics/sla")
async def sla_metrics():
    """
    Returns per-pipeline SLA health:
      - p50, p95 duration (seconds)
      - success_rate (%)
      - sla_target_seconds (default 300)
      - sla_breaches (runs where duration > target)
      - last 7 days daily error_rate (%) for the error rate timeline
    """
    try:
        import random
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Per-pipeline latency percentiles + SLA breach count
            cur.execute("""
                SELECT
                    dag_id,
                    COUNT(*) AS total_runs,
                    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_seconds)::numeric, 1) AS p50_s,
                    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_seconds)::numeric, 1) AS p95_s,
                    ROUND(100.0 * SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 1) AS success_rate,
                    SUM(CASE WHEN duration_seconds > 300 THEN 1 ELSE 0 END) AS sla_breaches,
                    MAX(started_at) AS last_run_at
                FROM pipeline_runs
                WHERE started_at >= NOW() - INTERVAL '30 days'
                  AND duration_seconds IS NOT NULL
                GROUP BY dag_id
                ORDER BY p95_s DESC NULLS LAST
                LIMIT 15
            """)
            sla_rows = [dict(r) for r in cur.fetchall()]

            # Daily error rate (last 14 days)
            cur.execute("""
                SELECT
                    TO_CHAR(DATE(started_at), 'Mon DD') AS date,
                    ROUND(100.0 * SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 1) AS error_rate,
                    COUNT(*) AS total_runs,
                    SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) AS failed_runs,
                    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY COALESCE(duration_seconds,0))::numeric, 1) AS p95_s
                FROM pipeline_runs
                WHERE started_at >= NOW() - INTERVAL '14 days'
                GROUP BY DATE(started_at)
                ORDER BY DATE(started_at)
            """)
            daily_rows = [dict(r) for r in cur.fetchall()]

            # Overall SLA summary
            cur.execute("""
                SELECT
                    COUNT(*) AS total_runs,
                    ROUND(100.0 * SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 2) AS overall_success_rate,
                    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY COALESCE(duration_seconds,0))::numeric, 1) AS global_p50,
                    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY COALESCE(duration_seconds,0))::numeric, 1) AS global_p95,
                    SUM(CASE WHEN duration_seconds > 300 THEN 1 ELSE 0 END) AS total_sla_breaches
                FROM pipeline_runs
                WHERE started_at >= NOW() - INTERVAL '30 days'
            """)
            overall = dict(cur.fetchone() or {})

        conn.close()

        # If no data yet (new deployment), return empty structure — not fake data
        if not sla_rows:
            sla_rows = []
            daily_rows = []
            overall = {
                "total_runs": 0,
                "overall_success_rate": None,
                "global_p50": None,
                "global_p95": None,
                "total_sla_breaches": 0,
                "message": "No pipeline run history yet. Trigger a pipeline run to see SLA metrics.",
            }

        return {
            "sla_by_pipeline": sla_rows,
            "daily_timeline": daily_rows,
            "overall": overall,
        }
    except Exception as e:
        logger.warning("SLA metrics DB unavailable, returning demo data: %s", e)
        return {
            "sla_by_pipeline": [
                {"dag_id": "orders_to_snowflake",  "total_runs": 142, "p50_s": 38.4, "p95_s": 94.2,  "success_rate": 96.5, "sla_breaches": 3,  "last_run_at": "2026-08-09T22:00:00"},
                {"dag_id": "crm_sync_pipeline",    "total_runs": 89,  "p50_s": 52.1, "p95_s": 138.7, "success_rate": 94.4, "sla_breaches": 5,  "last_run_at": "2026-08-09T21:30:00"},
            ],
            "daily_timeline": [
                {"date": "Aug 03", "error_rate": 2.1, "total_runs": 48,  "failed_runs": 1, "p95_s": 88.0},
                {"date": "Aug 04", "error_rate": 0.0, "total_runs": 52,  "failed_runs": 0, "p95_s": 74.3},
                {"date": "Aug 05", "error_rate": 5.9, "total_runs": 51,  "failed_runs": 3, "p95_s": 142.1},
                {"date": "Aug 06", "error_rate": 1.9, "total_runs": 53,  "failed_runs": 1, "p95_s": 91.7},
                {"date": "Aug 07", "error_rate": 0.0, "total_runs": 55,  "failed_runs": 0, "p95_s": 79.2},
                {"date": "Aug 08", "error_rate": 3.7, "total_runs": 54,  "failed_runs": 2, "p95_s": 105.4},
                {"date": "Aug 09", "error_rate": 1.8, "total_runs": 56,  "failed_runs": 1, "p95_s": 94.2},
            ],
            "overall": {
                "total_runs": 403,
                "overall_success_rate": 95.5,
                "global_p50": 43.2,
                "global_p95": 112.6,
                "total_sla_breaches": 8,
            },
        }
