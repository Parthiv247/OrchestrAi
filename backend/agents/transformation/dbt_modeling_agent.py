"""
DbtModelingAgent — LangGraph agent that auto-generates and runs dbt models.

6 nodes: introspect_schema → propose_star_schema → generate_staging_models
       → generate_mart_models → run_dbt → report
"""
import json
import logging
import os
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

import httpx
import psycopg2
import psycopg2.extras
import psycopg2.sql
from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

DBT_PROJECT_DIR = Path(__file__).parent.parent.parent.parent / "dbt_project"
STAGING_DIR     = DBT_PROJECT_DIR / "models" / "staging"
MARTS_DIR       = DBT_PROJECT_DIR / "models" / "marts"

DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST", "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname":   os.getenv("POSTGRES_DB", "orchestrai"),
    "user":     os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}

RAW_TABLES = ["nyc_taxi_trips", "ecommerce_orders"]


# ── Shared state ───────────────────────────────────────────────────────────────

class DbtAgentState(TypedDict):
    raw_tables: list[str]
    schema_info: dict[str, Any] | None        # table → {columns, row_count, sample}
    star_schema_proposal: dict[str, Any] | None  # {fact_tables, dimension_tables, reasoning}
    staging_models: dict[str, str] | None     # model_name → SQL
    mart_models: dict[str, str] | None        # model_name → SQL
    written_files: list[str] | None
    dbt_run_output: str | None
    dbt_test_output: str | None
    models_succeeded: int
    models_failed: int
    tests_passed: int
    tests_failed: int
    mart_tables_created: list[str] | None
    run_id: str | None
    error: str | None
    started_at: str


class DbtModelingAgent:
    """LangGraph-based dbt modeling agent: introspect → propose → generate → run → report."""

    def __init__(self):
        self.graph = self._build_graph()

    # ── Graph ──────────────────────────────────────────────────────────────────

    def _build_graph(self):
        g = StateGraph(DbtAgentState)
        g.add_node("introspect_schema",        self._node_introspect)
        g.add_node("propose_star_schema",      self._node_propose)
        g.add_node("generate_staging_models",  self._node_staging)
        g.add_node("generate_mart_models",     self._node_marts)
        g.add_node("run_dbt",                  self._node_run_dbt)
        g.add_node("report",                   self._node_report)
        g.set_entry_point("introspect_schema")
        g.add_edge("introspect_schema",       "propose_star_schema")
        g.add_edge("propose_star_schema",     "generate_staging_models")
        g.add_edge("generate_staging_models", "generate_mart_models")
        g.add_edge("generate_mart_models",    "run_dbt")
        g.add_edge("run_dbt",                 "report")
        g.add_edge("report",                  END)
        return g.compile()

    # ── Nodes ──────────────────────────────────────────────────────────────────

    def _node_introspect(self, state: DbtAgentState) -> DbtAgentState:
        """Fetch column types, row counts, and sample rows for each raw table."""
        schema_info = {}
        tables = state.get("raw_tables") or RAW_TABLES
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                for table in tables:
                    # Columns
                    cur.execute("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = 'raw' AND table_name = %s
                        ORDER BY ordinal_position
                    """, (table,))
                    cols = [dict(r) for r in cur.fetchall()]
                    # Row count
                    cur.execute(
                        psycopg2.sql.SQL("SELECT COUNT(*) AS count FROM raw.{}").format(
                            psycopg2.sql.Identifier(table)
                        )
                    )
                    _cnt_row = cur.fetchone()
                    row_count = _cnt_row["count"] if _cnt_row else 0
                    # Sample (3 rows)
                    cur.execute(
                        psycopg2.sql.SQL("SELECT * FROM raw.{} LIMIT 3").format(
                            psycopg2.sql.Identifier(table)
                        )
                    )
                    sample = [dict(r) for r in cur.fetchall()]
                    schema_info[table] = {
                        "columns": cols,
                        "row_count": row_count,
                        "sample": sample,
                    }
            conn.close()
            logger.info("Introspected %d tables", len(schema_info))
        except Exception as e:
            logger.error("introspect_schema failed: %s", e)
            return {**state, "error": str(e)}
        return {**state, "schema_info": schema_info}

    def _node_propose(self, state: DbtAgentState) -> DbtAgentState:
        """Ask Groq to propose a star schema from the raw table schemas."""
        schema_info = state.get("schema_info") or {}
        compact = {}
        for tbl, info in schema_info.items():
            compact[tbl] = {
                "row_count": info["row_count"],
                "columns": [f"{c['column_name']} ({c['data_type']})" for c in info["columns"][:20]],
            }

        prompt = f"""You are a senior analytics engineer. Given these raw tables, propose a star schema.

Raw tables:
{json.dumps(compact, indent=2)}

Return ONLY valid JSON (no markdown fences):
{{
  "fact_tables": [
    {{"name": "fct_trips", "description": "...", "grain": "one row per trip",
      "measures": ["fare_amount", "trip_distance_miles"],
      "foreign_keys": ["pu_location_id", "do_location_id"]}}
  ],
  "dimension_tables": [
    {{"name": "dim_customers", "description": "...", "columns": ["customer_id", "segment"],
      "primary_key": "customer_id"}}
  ],
  "reasoning": "one paragraph"
}}"""

        try:
            proposal = self._call_groq(prompt, max_tokens=800)
            parsed = self._parse_json(proposal)
        except Exception as e:
            logger.warning("propose_star_schema Groq call failed: %s — using default", e)
            parsed = {
                "fact_tables": [
                    {"name": "fct_trips", "description": "NYC Taxi trip facts", "grain": "one row per trip",
                     "measures": ["fare_amount", "total_amount", "trip_distance_miles"],
                     "foreign_keys": ["pu_location_id", "do_location_id"]},
                    {"name": "fct_ecommerce_summary", "description": "E-commerce daily revenue summary",
                     "grain": "one row per day/category/city",
                     "measures": ["total_revenue", "order_count"], "foreign_keys": ["customer_id"]},
                ],
                "dimension_tables": [
                    {"name": "dim_customers", "description": "Customer dimension with LTV",
                     "columns": ["customer_id", "total_revenue", "customer_segment"],
                     "primary_key": "customer_id"},
                    {"name": "dim_taxi_zones", "description": "Taxi zone traffic statistics",
                     "columns": ["location_id", "zone_tier", "total_trips"],
                     "primary_key": "location_id"},
                ],
                "reasoning": "Default star schema for NYC Taxi + E-commerce datasets.",
            }
        return {**state, "star_schema_proposal": parsed}

    def _node_staging(self, state: DbtAgentState) -> DbtAgentState:
        """Generate staging model SQL for each raw table (using existing or Groq-generated)."""
        schema_info = state.get("schema_info") or {}
        staging_models: dict[str, str] = {}
        written: list[str] = []

        for table_name, info in schema_info.items():
            model_name = f"stg_{table_name}"
            existing = STAGING_DIR / f"{model_name}.sql"
            # Keep existing hand-crafted staging models if they exist
            if existing.exists():
                staging_models[model_name] = existing.read_text()
                logger.info("Keeping existing staging model: %s", model_name)
                continue

            # Generate with Groq
            col_summary = ", ".join(
                c["column_name"] for c in info["columns"][:25]
            )
            sql = self.generate_for_table(table_name, col_summary)
            # Optimize generated SQL before writing to disk — logs savings to DB
            try:
                from ..optimization.cost_optimizer_agent import CostOptimizerAgent
                opt_result = CostOptimizerAgent().optimize(sql, context=f"dbt:staging:{model_name}")
                if opt_result.optimized_sql and not opt_result.error:
                    sql = opt_result.optimized_sql
                    logger.info("dbt staging model %s optimized — saved $%.4f", model_name, opt_result.dollar_savings)
            except Exception as _oe:
                logger.warning("dbt staging optimizer failed for %s: %s", model_name, _oe)
            path = STAGING_DIR / f"{model_name}.sql"
            path.write_text(sql)
            staging_models[model_name] = sql
            written.append(str(path))
            logger.info("Generated staging model: %s", model_name)

        return {**state, "staging_models": staging_models, "written_files": written}

    def _node_marts(self, state: DbtAgentState) -> DbtAgentState:
        """Generate mart model SQL for each fact/dimension in the star schema proposal."""
        proposal = state.get("star_schema_proposal") or {}
        mart_models: dict[str, str] = {}
        written = list(state.get("written_files") or [])

        all_mart_tables = (
            proposal.get("fact_tables", []) +
            proposal.get("dimension_tables", [])
        )

        for spec in all_mart_tables:
            model_name = spec.get("name", "")
            if not model_name:
                continue
            existing = MARTS_DIR / f"{model_name}.sql"
            if existing.exists():
                mart_models[model_name] = existing.read_text()
                logger.info("Keeping existing mart model: %s", model_name)
                continue

            # Generate with Groq
            prompt = f"""Write a dbt SQL model named {model_name}.
Description: {spec.get('description', '')}
Available staging models (use {{ ref('stg_...') }}):
  - stg_nyc_taxi_trips (trip_id, vendor_name, pickup_at, pickup_hour, trip_distance_miles, fare_amount, tip_amount, total_amount, payment_method, is_airport_trip, pu_location_id, do_location_id)
  - stg_ecommerce_orders (order_key, order_id, customer_id, product_name, category, unit_price, quantity, total_amount, status, is_completed, city, ordered_at, order_month_key)

Write ONLY the SQL, starting with {{{{ config(materialized='table', schema='marts') }}}}.
No markdown, no explanation."""

            try:
                sql = self._call_groq(prompt, max_tokens=800)
                sql = re.sub(r"```sql\n?|```\n?", "", sql).strip()
            except Exception as e:
                logger.warning("Groq mart generation failed for %s: %s", model_name, e)
                sql = f"-- {model_name}: generation failed\nSELECT 1 AS placeholder"

            # Optimize generated SQL before writing to disk — logs savings to DB
            try:
                from ..optimization.cost_optimizer_agent import CostOptimizerAgent
                _opt = CostOptimizerAgent().optimize(sql, context=f"dbt:mart:{model_name}")
                if _opt.optimized_sql and not _opt.error:
                    sql = _opt.optimized_sql
                    logger.info("dbt mart model %s optimized — saved $%.4f", model_name, _opt.dollar_savings)
            except Exception as _oe:
                logger.warning("dbt mart optimizer failed for %s: %s", model_name, _oe)

            # Optimize generated mart SQL before writing — logs savings to DB
            try:
                from ..optimization.cost_optimizer_agent import CostOptimizerAgent
                opt_result = CostOptimizerAgent().optimize(sql, context=f"dbt:mart:{model_name}")
                if opt_result.optimized_sql and not opt_result.error:
                    sql = opt_result.optimized_sql
                    logger.info("dbt mart model %s optimized — saved $%.4f", model_name, opt_result.dollar_savings)
            except Exception as _oe:
                logger.warning("dbt mart optimizer failed for %s: %s", model_name, _oe)
            path = MARTS_DIR / f"{model_name}.sql"
            path.write_text(sql)
            mart_models[model_name] = sql
            written.append(str(path))
            logger.info("Generated mart model: %s", model_name)

        return {**state, "mart_models": mart_models, "written_files": written}

    def _node_run_dbt(self, state: DbtAgentState) -> DbtAgentState:
        """Execute dbt run and dbt test, parse results."""
        run_stdout, run_stderr, run_code = self.run_dbt_command("run")
        run_output = run_stdout + run_stderr

        # Parse success/fail counts
        succeeded = len(re.findall(r"\bOK\b", run_output))
        failed    = len(re.findall(r"\bERROR\b", run_output))

        test_stdout, test_stderr, _ = self.run_dbt_command("test")
        test_output = test_stdout + test_stderr
        tests_pass = len(re.findall(r"PASS", test_output))
        tests_fail = len(re.findall(r"FAIL|ERROR", test_output))

        # Collect mart tables created
        mart_tables = [
            m.group(1)
            for m in re.finditer(r"marts\.(\w+)", run_output)
        ]

        # Persist run to DB
        run_id = self._save_dbt_run(
            models_generated=len(state.get("staging_models") or {}) + len(state.get("mart_models") or {}),
            models_succeeded=succeeded,
            models_failed=failed,
            tests_passed=tests_pass,
            tests_failed=tests_fail,
            mart_tables=mart_tables,
            run_output=run_output[:5000],
        )

        return {**state,
                "dbt_run_output": run_output[:5000],
                "dbt_test_output": test_output[:2000],
                "models_succeeded": succeeded,
                "models_failed": failed,
                "tests_passed": tests_pass,
                "tests_failed": tests_fail,
                "mart_tables_created": list(set(mart_tables)),
                "run_id": run_id,
                }

    def _node_report(self, state: DbtAgentState) -> DbtAgentState:
        logger.info(
            "DbtModelingAgent complete: %d models succeeded, %d failed, %d tests passed",
            state.get("models_succeeded", 0),
            state.get("models_failed", 0),
            state.get("tests_passed", 0),
        )
        return state

    # ── Public entry points ────────────────────────────────────────────────────

    def run(self, raw_tables: list[str] | None = None) -> DbtAgentState:
        initial = DbtAgentState(
            raw_tables=raw_tables or RAW_TABLES,
            schema_info=None,
            star_schema_proposal=None,
            staging_models=None,
            mart_models=None,
            written_files=None,
            dbt_run_output=None,
            dbt_test_output=None,
            models_succeeded=0,
            models_failed=0,
            tests_passed=0,
            tests_failed=0,
            mart_tables_created=None,
            run_id=None,
            error=None,
            started_at=datetime.utcnow().isoformat(),
        )
        return self.graph.invoke(initial)

    def generate_for_table(self, table_name: str, columns: str) -> str:
        """Generate a dbt staging model for a given raw table."""
        prompt = f"""Write a dbt staging model for the table raw.{table_name}.
Columns: {columns}
Rules: use {{{{ source('orchestrai', '{table_name}') }}}}, rename to snake_case,
cast types, add config(materialized='view', schema='staging').
Return ONLY SQL, no markdown."""
        try:
            sql = self._call_groq(prompt, max_tokens=600)
            return re.sub(r"```sql\n?|```\n?", "", sql).strip()
        except Exception:
            return f"{{{{ config(materialized='view', schema='staging') }}}}\nSELECT * FROM {{{{ source('orchestrai', '{table_name}') }}}}"

    def run_dbt_command(self, command: str) -> tuple:
        """Run `dbt <command>` in the dbt project directory."""
        try:
            result = subprocess.run(
                ["dbt", command,
                 "--profiles-dir", str(DBT_PROJECT_DIR),
                 "--project-dir", str(DBT_PROJECT_DIR),
                 "--no-use-colors"],
                cwd=str(DBT_PROJECT_DIR),
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ,
                     "POSTGRES_HOST": os.getenv("POSTGRES_HOST", "localhost"),
                     "POSTGRES_PORT": os.getenv("POSTGRES_PORT", "5432"),
                     "POSTGRES_DB":   os.getenv("POSTGRES_DB", "orchestrai"),
                     "POSTGRES_USER": os.getenv("POSTGRES_USER", "admin"),
                     "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
                     },
            )
            return result.stdout, result.stderr, result.returncode
        except FileNotFoundError:
            return "", "dbt not found in PATH", -1
        except subprocess.TimeoutExpired:
            return "", "dbt command timed out (300s)", -1
        except Exception as e:
            return "", str(e), -1

    # ── DB persistence ─────────────────────────────────────────────────────────

    def _save_dbt_run(self, **kwargs) -> str:
        run_id = str(uuid.uuid4())
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO dbt_runs
                      (id, triggered_by, models_generated, models_succeeded, models_failed,
                       tests_passed, tests_failed, mart_tables_created, run_output, created_at)
                    VALUES (%s, 'DbtModelingAgent', %s, %s, %s, %s, %s, %s::jsonb, %s, NOW())
                """, (
                    run_id,
                    kwargs.get("models_generated", 0),
                    kwargs.get("models_succeeded", 0),
                    kwargs.get("models_failed", 0),
                    kwargs.get("tests_passed", 0),
                    kwargs.get("tests_failed", 0),
                    json.dumps(kwargs.get("mart_tables", [])),
                    kwargs.get("run_output", "")[:5000],
                ))
                conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Failed to save dbt_run record: %s", e)
        return run_id

    # ── Groq helpers ───────────────────────────────────────────────────────────

    def _call_groq(self, prompt: str, max_tokens: int = 800) -> str:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set")
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.1, "max_tokens": max_tokens},
            timeout=40.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _parse_json(self, text: str) -> dict[str, Any]:
        # Try to extract JSON from response
        text = re.sub(r"```json\n?|```\n?", "", text).strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}
