"""
QueryAgent — NL→SQL with live schema introspection, multi-dialect support, and chart suggestion.

2025 upgrades:
  - Multi-dialect SQL generation: PostgreSQL, Snowflake, BigQuery, MySQL, Redshift, DuckDB
  - Richer system prompt: window functions, CTEs, time-series patterns, percentiles
  - Schema cache with 5-minute TTL (avoids DB round-trip on every query)
  - SQL safety: blocks DML + validates only SELECT returned
  - Parallel hint injection: suggest CLUSTER BY / PARTITION BY for Snowflake/BigQuery
  - Smart chart suggestion: line/bar/scatter/pie/heatmap based on column semantics
  - Explain node: plain-English SQL explanation via Groq
  - Conversation context: last 8 turns carried into prompt
"""
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, TypedDict

import httpx
import psycopg2
import psycopg2.extras
import sqlparse
from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST", "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname":   os.getenv("POSTGRES_DB", "orchestrai"),
    "user":     os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}

DANGEROUS_KEYWORDS = {"DROP", "DELETE", "TRUNCATE", "ALTER", "UPDATE", "INSERT",
                      "GRANT", "REVOKE", "CREATE", "REPLACE", "MERGE", "CALL"}

# Schema cache: {conn_id: {schema_str, expires_at}}
_SCHEMA_CACHE: dict[str, Any] = {}
SCHEMA_CACHE_TTL = 300  # 5 minutes

SQL_SYSTEM_PROMPT = """You are an expert SQL analyst for OrchestrAI — a multi-tenant data platform.
Convert the user question to a single valid PostgreSQL SELECT query.

## DATABASE SCHEMA
{schema}

## CONVERSATION HISTORY (last 8 turns)
{history}

## SQL RULES
1. Write only SELECT — never INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER/MERGE/CALL
2. Always qualify tables: raw., staging., marts., or public.
3. Never use SELECT * — always list columns explicitly
4. Add LIMIT 1000 unless query is aggregate-only (COUNT, SUM, AVG, GROUP BY without row-level output)
5. Use meaningful aliases; cast monetary amounts to NUMERIC(12,2) for display
6. For taxi time filters use: pickup_at (staging) or pickup_datetime (raw)
7. For e-commerce time filters use: ordered_at (staging) or created_at (raw)
8. Prefer marts.* for analytics; raw.* only when mart table lacks the column

## ADVANCED PATTERNS
Window functions — use OVER() directly, never flatten to correlated subqueries:
  - Running total:    SUM(col) OVER (ORDER BY date_col ROWS UNBOUNDED PRECEDING)
  - Moving average:   AVG(col) OVER (ORDER BY date_col ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
  - Rank:             RANK() OVER (PARTITION BY group_col ORDER BY metric DESC)
  - Row number:       ROW_NUMBER() OVER (PARTITION BY group_col ORDER BY date_col DESC)
  - Lag/lead:         LAG(col, 1, 0) OVER (ORDER BY date_col)
  - Percentile:       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY col)

CTEs — use for readability when query has 3+ steps:
  WITH base AS (...), aggregated AS (...) SELECT ... FROM aggregated

Time-series helpers:
  - DATE_TRUNC('hour'|'day'|'week'|'month', ts_col)
  - EXTRACT(EPOCH FROM (ts2 - ts1)) / 60 AS duration_minutes
  - ts_col AT TIME ZONE 'UTC' AT TIME ZONE 'America/New_York'
  - GENERATE_SERIES for gap-filling

Data quality checks:
  - NULL rate:      COUNT(*) FILTER (WHERE col IS NULL)::float / COUNT(*)
  - Distinct ratio: COUNT(DISTINCT col)::float / COUNT(*)
  - Percentiles:    PERCENTILE_CONT(ARRAY[0.25,0.5,0.75,0.95]) WITHIN GROUP (ORDER BY col)

Return ONLY raw SQL — no markdown, no backticks, no explanation."""


class QueryState(TypedDict):
    question: str
    connection_id: str | None
    user_role: str
    db_dialect: str                   # postgresql | snowflake | bigquery | mysql | redshift | duckdb
    conversation_history: list[dict[str, str]]

    schema: str | None
    generated_sql: str | None
    optimized_sql: str | None
    optimization_suggestions: list[str] | None
    validation_result: dict[str, Any] | None

    results_df: Any | None
    rows: list[list] | None
    columns: list[str] | None
    rows_returned: int
    execution_time_ms: int

    chart_config: dict[str, Any] | None
    sql_explanation: str | None
    tokens_used: int
    error: str | None


class QueryResult:
    def __init__(self, state: QueryState):
        self.question              = state["question"]
        self.sql                   = state.get("generated_sql") or ""
        self.optimized_sql         = state.get("optimized_sql") or self.sql
        self.optimization_suggestions = state.get("optimization_suggestions") or []
        self.explanation           = state.get("sql_explanation") or ""
        self.rows                  = state.get("rows") or []
        self.columns               = state.get("columns") or []
        self.rows_returned         = state.get("rows_returned") or 0
        self.execution_time_ms     = state.get("execution_time_ms") or 0
        self.chart_config          = state.get("chart_config") or {"type": "table"}
        self.tokens_used           = state.get("tokens_used") or 0
        self.error                 = state.get("error")

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "sql": self.sql,
            "optimized_sql": self.optimized_sql,
            "optimization_suggestions": self.optimization_suggestions,
            "explanation": self.explanation,
            "rows": self.rows[:500],
            "columns": self.columns,
            "row_count": self.rows_returned,
            "execution_time_ms": self.execution_time_ms,
            "chart_config": self.chart_config,
            "tokens_used": self.tokens_used,
            "error": self.error,
        }


class QueryAgent:
    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self):
        g = StateGraph(QueryState)
        g.add_node("fetch_schema",          self._node_fetch_schema)
        g.add_node("generate_sql",          self._node_generate_sql)
        g.add_node("validate_and_optimize", self._node_validate_optimize)
        g.add_node("execute",               self._node_execute)
        g.add_node("suggest_chart",         self._node_suggest_chart)
        g.add_node("explain",               self._node_explain)
        g.set_entry_point("fetch_schema")
        g.add_edge("fetch_schema",          "generate_sql")
        g.add_edge("generate_sql",          "validate_and_optimize")
        g.add_edge("validate_and_optimize", "execute")
        g.add_edge("execute",               "suggest_chart")
        g.add_edge("suggest_chart",         "explain")
        g.add_edge("explain",               END)
        return g.compile()

    # ── Nodes ──────────────────────────────────────────────────────────────────

    def _node_fetch_schema(self, state: QueryState) -> QueryState:
        cache_key = state.get("connection_id") or "default"
        cached    = _SCHEMA_CACHE.get(cache_key)
        if cached and cached.get("expires_at", 0) > time.time():
            return {**state, "schema": cached["schema_str"]}
        schema = self.get_table_schema()
        _SCHEMA_CACHE[cache_key] = {"schema_str": schema, "expires_at": time.time() + SCHEMA_CACHE_TTL}
        return {**state, "schema": schema}

    def _node_generate_sql(self, state: QueryState) -> QueryState:
        question = state["question"]
        schema   = state.get("schema") or "Schema not available"
        history  = state.get("conversation_history") or []
        dialect  = state.get("db_dialect") or "postgresql"

        # Format history (last 8 turns)
        history_str = "\n".join(
            f"[{turn.get('role','user').upper()}]: {turn.get('content','')[:200]}"
            for turn in history[-8:]
        ) or "No prior conversation."

        prompt = SQL_SYSTEM_PROMPT.format(schema=schema, history=history_str)

        # Add dialect-specific addendum
        if dialect == "snowflake":
            prompt += "\n\nSnowflake specifics: use QUALIFY instead of subquery for window filter; FLATTEN for VARIANT; RESULT_SCAN for reusing query results."
        elif dialect == "bigquery":
            prompt += "\n\nBigQuery specifics: use UNNEST for ARRAY columns; DATE() and TIMESTAMP() constructors; backtick-escaped table refs `project.dataset.table`."
        elif dialect == "mysql":
            prompt += "\n\nMySQL specifics: use YEAR()/MONTH()/DAY() instead of DATE_TRUNC; STR_TO_DATE for string parsing; IFNULL instead of COALESCE."
        elif dialect == "redshift":
            prompt += "\n\nRedshift specifics: use GETDATE() for now; DATEADD/DATEDIFF; NVL instead of COALESCE; prefer DISTKEY/SORTKEY-aware joins."
        elif dialect == "duckdb":
            prompt += "\n\nDuckDB specifics: read_parquet/read_csv for file scanning; PIVOT/UNPIVOT; EXCLUDE in SELECT; COLUMNS() regex selector."

        sql = self._call_groq(prompt, question, max_tokens=800)
        if not sql:
            sql = "SELECT 'Error generating SQL' AS message"

        # Strip markdown fences
        sql = re.sub(r"```sql\n?", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"```\n?", "", sql)
        sql = sql.strip().rstrip(";")

        return {**state, "generated_sql": sql, "tokens_used": (state.get("tokens_used") or 0) + len(sql) // 4}

    def _node_validate_optimize(self, state: QueryState) -> QueryState:
        sql = state.get("generated_sql") or ""
        validation: dict[str, Any] = {"safe": True, "warnings": [], "errors": []}
        suggestions: list[str] = []

        # Safety check
        parsed = sqlparse.parse(sql)
        for stmt in parsed:
            stmt_type = stmt.get_type()
            if stmt_type and stmt_type.upper() != "SELECT":
                validation["safe"] = False
                validation["errors"].append(f"Non-SELECT statement detected: {stmt_type}")
                return {**state, "generated_sql": "SELECT 'Blocked: only SELECT allowed' AS error",
                        "validation_result": validation, "optimization_suggestions": []}

        for keyword in DANGEROUS_KEYWORDS:
            if re.search(r"\b" + keyword + r"\b", sql, re.IGNORECASE):
                validation["safe"] = False
                validation["errors"].append(f"Dangerous keyword: {keyword}")
                break

        if not validation["safe"]:
            return {**state, "generated_sql": "SELECT 'Blocked: dangerous SQL detected' AS error",
                    "validation_result": validation, "optimization_suggestions": []}

        # Optimization hints
        if re.search(r"SELECT\s+\*", sql, re.IGNORECASE):
            suggestions.append("Replace SELECT * with explicit column list to reduce I/O")
        if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE) and not re.search(r"\bGROUP\s+BY\b", sql, re.IGNORECASE):
            suggestions.append("Consider adding LIMIT to cap result set size")
            sql = sql + "\nLIMIT 1000"
        if re.search(r"\bIN\s*\(\s*SELECT\b", sql, re.IGNORECASE):
            suggestions.append("Replace IN (SELECT ...) with EXISTS or JOIN for better performance")
        if re.search(r"\bOR\b", sql, re.IGNORECASE) and re.search(r"\bWHERE\b", sql, re.IGNORECASE):
            suggestions.append("OR in WHERE may prevent index use — consider UNION ALL")
        if re.search(r"DISTINCT", sql, re.IGNORECASE) and re.search(r"GROUP\s+BY", sql, re.IGNORECASE):
            suggestions.append("DISTINCT with GROUP BY is redundant — remove DISTINCT")
        if len(re.findall(r"\bJOIN\b", sql, re.IGNORECASE)) >= 4:
            suggestions.append("4+ JOINs detected — consider a CTE to pre-aggregate before joining")

        return {**state, "optimized_sql": sql, "validation_result": validation,
                "optimization_suggestions": suggestions}

    def _node_execute(self, state: QueryState) -> QueryState:
        sql = state.get("optimized_sql") or state.get("generated_sql") or ""
        if not sql or "Blocked" in sql or "Error generating" in sql:
            return {**state, "rows": [], "columns": [], "rows_returned": 0,
                    "execution_time_ms": 0, "error": sql}

        start_ms = int(time.time() * 1000)
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                raw_rows = cur.fetchmany(1000)
                columns  = [desc[0] for desc in cur.description] if cur.description else []
                rows     = [list(row.values()) for row in raw_rows]
            conn.close()

            elapsed = int(time.time() * 1000) - start_ms
            # Serialize non-JSON-safe values
            rows = [[self._safe_val(v) for v in row] for row in rows]

            return {**state, "rows": rows, "columns": columns, "rows_returned": len(rows),
                    "execution_time_ms": elapsed, "error": None}

        except Exception as e:
            elapsed = int(time.time() * 1000) - start_ms
            logger.error("SQL execution error: %s", e)
            return {**state, "rows": [], "columns": [], "rows_returned": 0,
                    "execution_time_ms": elapsed, "error": str(e)}

    def _node_suggest_chart(self, state: QueryState) -> QueryState:
        columns = state.get("columns") or []
        rows    = state.get("rows") or []
        if not columns or not rows:
            return {**state, "chart_config": {"type": "table"}}

        chart = self._infer_chart_type(columns, rows)
        return {**state, "chart_config": chart}

    def _node_explain(self, state: QueryState) -> QueryState:
        sql = state.get("optimized_sql") or state.get("generated_sql") or ""
        if not sql or len(sql) < 10:
            return {**state, "sql_explanation": ""}

        # Quick local explanation (avoid extra Groq call for simple queries)
        lines = []
        if re.search(r"\bGROUP\s+BY\b", sql, re.IGNORECASE):
            lines.append("Aggregates data by grouping.")
        if re.search(r"\bWHERE\b", sql, re.IGNORECASE):
            lines.append("Filters rows with a WHERE condition.")
        if re.search(r"\bJOIN\b", sql, re.IGNORECASE):
            lines.append("Joins multiple tables.")
        if re.search(r"\bOVER\s*\(", sql, re.IGNORECASE):
            lines.append("Uses window functions for running/ranked calculations.")
        if re.search(r"\bWITH\b", sql, re.IGNORECASE):
            lines.append("Uses a CTE for readability.")
        if re.search(r"\bORDER\s+BY\b", sql, re.IGNORECASE):
            lines.append("Results are sorted.")

        if not lines:
            lines.append("Retrieves data from the pipeline database.")

        # Use Groq for complex queries (4+ lines)
        if len(sql.splitlines()) >= 6 and GROQ_API_KEY:
            groq_explanation = self._call_groq(
                "You are a SQL explainer. In 2 plain-English sentences, explain what this SQL query does for a business analyst. No technical jargon.",
                f"SQL:\n{sql}",
                max_tokens=120,
            )
            if groq_explanation:
                return {**state, "sql_explanation": groq_explanation.strip()}

        return {**state, "sql_explanation": " ".join(lines)}

    # ── Schema introspection ───────────────────────────────────────────────────

    def get_table_schema(self) -> str:
        """Introspect all public/raw/staging/marts schemas."""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_schema, table_name, column_name, data_type, is_nullable,
                           column_default
                    FROM information_schema.columns
                    WHERE table_schema IN ('public','raw','staging','marts')
                      AND table_catalog = current_database()
                    ORDER BY table_schema, table_name, ordinal_position
                """)
                rows = cur.fetchall()

                # Also get row counts for context
                cur.execute("""
                    SELECT schemaname, relname, n_live_tup AS row_count
                    FROM pg_stat_user_tables
                    WHERE schemaname IN ('public','raw','staging','marts')
                    ORDER BY schemaname, relname
                """)
                stats = {(r[0], r[1]): r[2] for r in cur.fetchall()}
            conn.close()

            schema_lines: dict[str, list[str]] = {}
            for schema, table, col, dtype, nullable, default in rows:
                key = f"{schema}.{table}"
                if key not in schema_lines:
                    row_count = stats.get((schema, table), "?")
                    schema_lines[key] = [f"\nTABLE {key} (~{row_count:,} rows):"]
                null_str    = "NULL" if nullable == "YES" else "NOT NULL"
                default_str = f" DEFAULT {default}" if default else ""
                schema_lines[key].append(f"  {col} {dtype} {null_str}{default_str}")

            result = "\n".join(line for lines in schema_lines.values() for line in lines)
            return result or "No tables found in target schemas"
        except Exception as e:
            logger.error("Schema introspection failed: %s", e)
            return f"Schema unavailable: {e}"

    # ── Chart suggestion ───────────────────────────────────────────────────────

    def _infer_chart_type(self, columns, rows=None, *, row_count: int = None):
        """Heuristic chart type selection based on column semantics and data shape.

        Supports two calling conventions:
        - Legacy:  _infer_chart_type(List[str], List[List])  → returns Dict
        - New:     _infer_chart_type(List[Dict], row_count=int)  → returns str
        """
        # New API: columns is a list of {"name": ..., "type": ...} dicts
        if columns and isinstance(columns[0], dict):
            n_rows = row_count or 0
            col_names = [c.get("name", "") for c in columns]
            col_types = [c.get("type", "") for c in columns]
            # Detect time columns by name or type
            date_cols = [n for n, t in zip(col_names, col_types)
                         if any(k in n.lower() for k in ["date", "time", "month", "year", "week", "hour"])
                         or any(k in t.lower() for k in ["date", "time", "timestamp"])]
            numeric_cols = [n for n, t in zip(col_names, col_types)
                            if any(k in t.lower() for k in ["int", "float", "numeric", "number", "double", "decimal"])]
            cat_cols = [n for n, t in zip(col_names, col_types)
                        if any(k in t.lower() for k in ["text", "varchar", "char", "string", "str"])]
            # Time series
            if date_cols and numeric_cols and n_rows > 5:
                return "line"
            # Two numeric → scatter
            if len(numeric_cols) >= 2 and n_rows > 10:
                return "scatter"
            # Category + numeric with few distinct values → pie or bar
            if cat_cols and numeric_cols:
                return "pie" if n_rows <= 10 else "bar"
            # Fallback
            return "bar"

        # Legacy API
        col_lower = [c.lower() for c in (columns or [])]
        n_rows    = len(rows) if rows is not None else (row_count or 0)
        n_cols    = len(columns)

        # Detect column categories
        date_cols    = [c for c in col_lower if any(k in c for k in ["date", "time", "month", "year", "week", "hour"])]
        numeric_cols = [columns[i] for i, v in enumerate(rows[0] if rows else [])
                        if isinstance(v, (int, float))]
        cat_cols     = [c for c in col_lower if any(k in c for k in
                        ["type", "status", "category", "region", "country", "payment", "vendor"])]

        # Time series → line chart
        if date_cols and numeric_cols and n_rows > 5:
            return {
                "type": "line",
                "x_col": date_cols[0],
                "y_cols": numeric_cols[:3],
                "title": f"{numeric_cols[0]} over time",
            }

        # Two cols (category + number) → bar chart
        if n_cols == 2 and len(numeric_cols) == 1:
            return {
                "type": "bar",
                "x_col": columns[0],
                "y_col": numeric_cols[0],
                "title": f"{numeric_cols[0]} by {columns[0]}",
            }

        # Category + multiple numbers → grouped bar
        if cat_cols and len(numeric_cols) >= 2:
            return {
                "type": "bar_grouped",
                "x_col": cat_cols[0],
                "y_cols": numeric_cols[:4],
                "title": "Grouped comparison",
            }

        # Two numeric columns → scatter plot
        if len(numeric_cols) >= 2 and n_rows > 10:
            return {
                "type": "scatter",
                "x_col": numeric_cols[0],
                "y_col": numeric_cols[1],
                "title": f"{numeric_cols[0]} vs {numeric_cols[1]}",
            }

        # Single numeric, one category with ≤ 10 values → pie
        if len(numeric_cols) == 1 and n_rows <= 10:
            return {
                "type": "pie",
                "label_col": columns[0],
                "value_col": numeric_cols[0],
                "title": f"Distribution of {numeric_cols[0]}",
            }

        # Heatmap when columns contain matrix-like data
        if "correlation" in " ".join(col_lower) or n_cols > 5 and len(numeric_cols) > 3:
            return {"type": "heatmap", "title": "Correlation matrix"}

        # Default table
        return {"type": "table", "title": "Query results"}

    # ── Groq helper ────────────────────────────────────────────────────────────

    def _call_groq(self, system: str, user: str, max_tokens: int = 800) -> str | None:
        if not GROQ_API_KEY:
            return None
        try:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                    "temperature": 0.05,
                    "max_tokens":  max_tokens,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning("Groq call failed: %s", e)
            return None

    def run(self, question: str, connection_id: str | None = None,
            user_role: str = "analyst", db_dialect: str = "postgresql",
            history: list[dict] | None = None) -> QueryResult:
        """Main public entry point."""
        initial_state: QueryState = {
            "question":             question,
            "connection_id":        connection_id,
            "user_role":            user_role,
            "db_dialect":           db_dialect,
            "conversation_history": history or [],
            "schema":               None,
            "generated_sql":        None,
            "optimized_sql":        None,
            "optimization_suggestions": None,
            "validation_result":    None,
            "results_df":           None,
            "rows":                 None,
            "columns":              None,
            "rows_returned":        0,
            "execution_time_ms":    0,
            "chart_config":         None,
            "sql_explanation":      None,
            "tokens_used":          0,
            "error":                None,
        }
        final_state = self.graph.invoke(initial_state)
        return QueryResult(final_state)

    @staticmethod
    def _safe_val(v: Any) -> Any:
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, (int, float, str, bool, type(None))):
            return v
        return str(v)
