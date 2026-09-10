"""
Schema introspection for QueryAgent.
Queries PostgreSQL information_schema and schema_registry to build
a rich textual schema description for LLM prompting.
"""
import os
from pathlib import Path

import psycopg2
import psycopg2.sql
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")


def get_sync_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "orchestrai"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
    )


def get_schema_for_llm(schemas: list[str] = None) -> str:
    """Build a human-readable schema description for LLM prompting.

    Returns:
        A string like:
            Table: raw.nyc_taxi_trips
              - pickup_datetime (TIMESTAMP): When the passenger was picked up. Example: 2024-01-15 08:32:00
              ...
    """
    if schemas is None:
        schemas = ["raw", "staging", "marts"]

    try:
        conn = get_sync_connection()
        cur = conn.cursor()

        # Get column info from information_schema
        cur.execute("""
            SELECT
                c.table_schema,
                c.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                sr.description,
                sr.example_values
            FROM information_schema.columns c
            LEFT JOIN public.schema_registry sr
                ON sr.schema_name = c.table_schema
               AND sr.table_name  = c.table_name
               AND sr.column_name = c.column_name
            WHERE c.table_schema = ANY(%s)
              AND c.table_name NOT LIKE 'pg_%'
            ORDER BY c.table_schema, c.table_name, c.ordinal_position
        """, (schemas,))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return _fallback_schema()

        # Group by table
        tables: dict[str, list] = {}
        for schema, table, col, dtype, nullable, desc, examples in rows:
            key = f"{schema}.{table}"
            tables.setdefault(key, []).append((col, dtype, nullable, desc, examples))

        lines = ["Available PostgreSQL tables:\n"]
        for table_name, cols in tables.items():
            lines.append(f"Table: {table_name}")
            for col, dtype, nullable, desc, examples in cols:
                null_str = "nullable" if nullable == "YES" else "not null"
                desc_str = f" — {desc}" if desc else ""
                ex_str = f". Example: {examples}" if examples else ""
                lines.append(f"  - {col} ({dtype}, {null_str}){desc_str}{ex_str}")
            lines.append("")

        # Add row counts for context
        try:
            conn2 = get_sync_connection()
            cur2 = conn2.cursor()
            lines.append("Approximate row counts:")
            for table_name in tables:
                schema, tbl = table_name.split(".", 1)
                try:
                    cur2.execute(
                        psycopg2.sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                            psycopg2.sql.Identifier(schema),
                            psycopg2.sql.Identifier(tbl),
                        )
                    )
                    _cnt = cur2.fetchone()
                    count = _cnt[0] if _cnt else 0
                    lines.append(f"  {table_name}: {count:,} rows")
                except Exception:
                    pass
            cur2.close()
            conn2.close()
        except Exception:
            pass

        return "\n".join(lines)

    except Exception:
        return _fallback_schema()


def _fallback_schema() -> str:
    """Fallback schema description when DB is not available."""
    return """Available PostgreSQL tables:

Table: raw.nyc_taxi_trips
  - id (bigint, not null) — Auto-increment primary key
  - vendor_id (integer, nullable) — 1=Creative Mobile Technologies, 2=VeriFone
  - pickup_datetime (timestamp, not null) — When the passenger was picked up. Example: 2024-01-15 08:32:00
  - dropoff_datetime (timestamp, not null) — When the passenger was dropped off. Example: 2024-01-15 08:58:00
  - passenger_count (double precision, nullable) — Number of passengers (1-6). Example: 1, 2, 3
  - trip_distance (double precision, not null) — Trip distance in miles. Example: 1.5, 3.2, 8.7
  - pu_location_id (integer, not null) — Pickup TLC Taxi Zone ID (1-265). Example: 132, 161, 237
  - do_location_id (integer, not null) — Dropoff TLC Taxi Zone ID (1-265). Example: 132, 161, 237
  - payment_type (integer, not null) — 1=Credit card, 2=Cash, 3=No charge, 4=Dispute. Example: 1, 2
  - fare_amount (double precision, not null) — Metered fare in USD. Example: 7.50, 12.00, 45.00
  - tip_amount (double precision, not null) — Tip amount in USD. Example: 1.50, 2.00, 5.00
  - total_amount (double precision, not null) — Total charged to passenger in USD. Example: 12.00, 18.50, 60.00

Table: raw.ecommerce_orders
  - id (bigint, not null) — Auto-increment primary key
  - order_id (varchar, not null) — Unique order identifier. Example: ORD-100001
  - customer_id (integer, not null) — Customer identifier (1-1000). Example: 42, 100, 537
  - product_name (varchar, not null) — Product name. Example: Laptop Pro 15, Yoga Mat
  - category (varchar, not null) — Product category. Example: Electronics, Clothing, Books
  - unit_price (numeric, not null) — Price per unit in USD. Example: 29.99, 149.99, 299.99
  - quantity (integer, not null) — Number of units ordered. Example: 1, 2, 3
  - total_amount (numeric, not null) — Total order value in USD. Example: 49.99, 299.98
  - status (varchar, not null) — Order status. Example: placed, shipped, delivered, cancelled
  - city (varchar, not null) — Customer city. Example: New York, Los Angeles, Chicago
  - created_at (timestamp, not null) — When the order was placed. Example: 2024-01-15 14:32:00

Table: marts.fct_trips
  - trip_id (bigint, not null) — Trip identifier
  - pickup_date (date, not null) — Date of pickup. Example: 2024-01-15
  - pickup_hour (integer, not null) — Hour of pickup (0-23). Example: 8, 17, 22
  - vendor_name (varchar) — Taxi vendor name. Example: Creative Mobile, VeriFone
  - trip_distance_miles (double precision) — Trip distance in miles
  - trip_duration_min (double precision) — Trip duration in minutes
  - fare_amount (numeric) — Base fare in USD
  - tip_amount (numeric) — Tip in USD
  - total_amount (numeric) — Total charged in USD
  - payment_method (varchar) — Credit Card, Cash, No Charge, Dispute
  - is_airport_trip (boolean) — True if pickup or dropoff is at JFK/LGA/EWR

Table: marts.dim_customers
  - customer_id (integer, not null) — Customer identifier
  - total_orders (integer) — Lifetime order count
  - total_revenue (numeric) — Lifetime revenue in USD
  - avg_order_value (numeric) — Average order value in USD
  - first_order_at (timestamp) — Date of first order
  - last_order_at (timestamp) — Date of most recent order
  - favorite_category (varchar) — Most ordered product category
  - preferred_city (varchar) — City with most orders
  - customer_segment (varchar) — VIP (>$1000), Regular (>$300), Occasional

Approximate row counts:
  raw.nyc_taxi_trips: 2,964,624 rows
  raw.ecommerce_orders: 50,000 rows
  marts.fct_trips: 2,800,000 rows
  marts.dim_customers: 1,000 rows
"""


def execute_sql_sync(sql: str, limit: int = 500) -> dict:
    """Execute a SELECT query and return results as a dict with columns and rows."""
    try:
        conn = get_sync_connection()
        cur = conn.cursor()

        # Safety: only allow SELECT
        stripped = sql.strip().upper().lstrip("--").strip()
        if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
            return {"error": "Only SELECT queries are permitted", "columns": [], "rows": []}

        # Add LIMIT if not already present
        if "LIMIT" not in sql.upper():
            sql = f"{sql.rstrip(';')} LIMIT {limit}"

        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

        # Get execution plan for cost display
        cur.execute(f"EXPLAIN (FORMAT JSON) {sql}")
        _plan_row = cur.fetchone()
        plan = _plan_row[0] if _plan_row else None
        estimated_cost = plan[0]["Plan"].get("Total Cost", 0) if plan else 0

        cur.close()
        conn.close()
        return {
            "columns": columns,
            "rows": [list(r) for r in rows],
            "row_count": len(rows),
            "estimated_cost": estimated_cost,
            "error": None,
        }
    except Exception as e:
        return {"columns": [], "rows": [], "row_count": 0, "estimated_cost": 0, "error": str(e)}


def get_explain_analyze(sql: str) -> str:
    """Run EXPLAIN ANALYZE and return output as text."""
    try:
        conn = get_sync_connection()
        cur = conn.cursor()
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {sql}")
        lines = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return "\n".join(lines)
    except Exception as e:
        return f"Could not run EXPLAIN ANALYZE: {e}"
