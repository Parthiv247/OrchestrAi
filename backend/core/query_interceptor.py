"""
Query Interceptor — wraps every SQL execution through the Cost Optimizer.
Import and use execute_optimized() instead of running SQL directly.
All optimizations are auto-logged to the query_optimizations table.
"""
import logging
import time
import os
import json
import uuid
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST", "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname":   os.getenv("POSTGRES_DB", "orchestrai"),
    "user":     os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}


def execute_optimized(sql: str, context: str = "manual", connection_id: str = None):
    """
    1. Run Cost Optimizer on the SQL
    2. Log the optimization + savings to DB
    3. Execute the OPTIMIZED SQL against PostgreSQL
    4. Return rows, columns, and optimization metadata
    """
    from ..agents.optimization.cost_optimizer_agent import CostOptimizerAgent

    optimizer = CostOptimizerAgent()
    try:
        result = optimizer.optimize(sql.strip(), connection_id=connection_id)
        optimized_sql = result.optimized_sql or sql
        dollar_savings = result.dollar_savings or 0.0
        savings_pct    = result.savings_percent or 0.0
        changes_made   = result.changes_made or []
        optimization_id = result.optimization_id or str(uuid.uuid4())
    except Exception as e:
        logger.warning("Optimizer failed (%s) — running original SQL", e)
        optimized_sql, dollar_savings, savings_pct, changes_made = sql, 0.0, 0.0, []
        optimization_id = str(uuid.uuid4())

    exec_start = time.time()
    rows, columns, error = [], [], None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(optimized_sql)
            if cur.description:
                columns = [d.name for d in cur.description]
                raw = cur.fetchmany(500)
                rows = [list(r.values()) for r in raw]
        conn.close()
    except Exception as e:
        logger.error("Query execution failed: %s", e)
        error = str(e)

    exec_ms = int((time.time() - exec_start) * 1000)

    _log_optimization(optimization_id, context, sql, optimized_sql, changes_made,
                      dollar_savings, savings_pct, exec_ms, len(rows), error)

    return {
        "rows": rows, "columns": columns, "row_count": len(rows),
        "execution_time_ms": exec_ms, "original_sql": sql, "optimized_sql": optimized_sql,
        "savings_percent": savings_pct, "dollar_savings": dollar_savings,
        "optimization_id": optimization_id, "changes_made": changes_made, "error": error,
    }


def log_dbt_model_optimization(model_name: str, original_sql: str, optimized_sql: str,
                                dollar_savings: float, savings_pct: float, changes: list):
    """Call this after optimizing a dbt model SQL (before writing to disk)."""
    _log_optimization(str(uuid.uuid4()), f"dbt:{model_name}", original_sql, optimized_sql,
                      changes, dollar_savings, savings_pct, 0, 0, None)


def _log_optimization(optimization_id, context, original_sql, optimized_sql,
                       changes_made, dollar_savings, savings_pct, exec_ms, row_count, error):
    """Write one optimization record to the query_optimizations table."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO query_optimizations
                    (id, context, original_sql, optimized_sql, changes_made,
                     dollar_savings, savings_percent, execution_time_ms, row_count, error, created_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (id) DO NOTHING
            """, (
                optimization_id, context,
                (original_sql or '')[:10000], (optimized_sql or '')[:10000],
                json.dumps(changes_made or []),
                dollar_savings, savings_pct, exec_ms, row_count, error,
            ))
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Failed to log optimization: %s", e)
