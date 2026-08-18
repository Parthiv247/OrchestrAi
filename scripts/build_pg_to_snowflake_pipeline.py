"""
Build a real Postgres -> Snowflake(simulated) pipeline.

Snowflake is simulated by the Postgres schema `snowflake_dest` (no SF creds present;
this is the project's documented fallback). We:
  1. Create 10 source tables in schema `pg_source`, 1000 rows each (10,000 total).
  2. Create 10 matching empty tables in schema `snowflake_dest`.
  3. ETL: extract from pg_source, load into snowflake_dest (counted row-by-row).
  4. Register the pipeline in `pipelines` + a successful `pipeline_runs` entry.
"""
import uuid
import time
import psycopg2

DSN = "postgresql://admin:orchestrai_secret@localhost:5432/orchestrai"

SRC_SCHEMA = "source_pg"
DST_SCHEMA = "snowflake_dest"
ROWS = 1000

# (table_name, columns-as-generate_series-SELECT). Each yields exactly ROWS rows.
TABLES = {
    "customers": """
        SELECT gs AS id,
               'Customer ' || gs AS full_name,
               'cust' || gs || '@example.com' AS email,
               (ARRAY['US','UK','IN','DE','CA','AU'])[1 + (gs % 6)] AS country,
               round((random()*5000)::numeric, 2) AS lifetime_value,
               NOW() - ((random()*365)::int || ' days')::interval AS created_at
        FROM generate_series(1,{n}) gs""",
    "orders": """
        SELECT gs AS id,
               1 + (gs % {n}) AS customer_id,
               round((random()*900 + 10)::numeric, 2) AS order_total,
               (ARRAY['pending','paid','shipped','delivered','cancelled'])[1 + (gs % 5)] AS status,
               NOW() - ((random()*180)::int || ' days')::interval AS created_at
        FROM generate_series(1,{n}) gs""",
    "products": """
        SELECT gs AS id,
               'SKU-' || lpad(gs::text, 6, '0') AS sku,
               'Product ' || gs AS name,
               round((random()*500 + 1)::numeric, 2) AS price,
               (ARRAY['electronics','apparel','home','toys','grocery'])[1 + (gs % 5)] AS category,
               NOW() - ((random()*400)::int || ' days')::interval AS created_at
        FROM generate_series(1,{n}) gs""",
    "order_items": """
        SELECT gs AS id,
               1 + (gs % {n}) AS order_id,
               1 + (gs % {n}) AS product_id,
               1 + (gs % 5) AS quantity,
               round((random()*200 + 1)::numeric, 2) AS unit_price,
               NOW() - ((random()*180)::int || ' days')::interval AS created_at
        FROM generate_series(1,{n}) gs""",
    "payments": """
        SELECT gs AS id,
               1 + (gs % {n}) AS order_id,
               round((random()*900 + 10)::numeric, 2) AS amount,
               (ARRAY['card','paypal','wire','upi','cod'])[1 + (gs % 5)] AS method,
               (ARRAY['authorized','captured','refunded','failed'])[1 + (gs % 4)] AS status,
               NOW() - ((random()*180)::int || ' days')::interval AS created_at
        FROM generate_series(1,{n}) gs""",
    "shipments": """
        SELECT gs AS id,
               1 + (gs % {n}) AS order_id,
               (ARRAY['fedex','ups','dhl','usps','bluedart'])[1 + (gs % 5)] AS carrier,
               'TRK' || lpad(gs::text, 9, '0') AS tracking_no,
               NOW() - ((random()*150)::int || ' days')::interval AS shipped_at,
               NOW() - ((random()*180)::int || ' days')::interval AS created_at
        FROM generate_series(1,{n}) gs""",
    "reviews": """
        SELECT gs AS id,
               1 + (gs % {n}) AS product_id,
               1 + (gs % {n}) AS customer_id,
               1 + (gs % 5) AS rating,
               'Review comment number ' || gs AS comment,
               NOW() - ((random()*200)::int || ' days')::interval AS created_at
        FROM generate_series(1,{n}) gs""",
    "inventory": """
        SELECT gs AS id,
               1 + (gs % {n}) AS product_id,
               (ARRAY['WH-EAST','WH-WEST','WH-NORTH','WH-SOUTH'])[1 + (gs % 4)] AS warehouse,
               (random()*1000)::int AS quantity_on_hand,
               NOW() - ((random()*90)::int || ' days')::interval AS created_at
        FROM generate_series(1,{n}) gs""",
    "suppliers": """
        SELECT gs AS id,
               'Supplier ' || gs AS name,
               (ARRAY['US','CN','IN','DE','VN','MX'])[1 + (gs % 6)] AS country,
               round((random()*5)::numeric, 2) AS rating,
               NOW() - ((random()*500)::int || ' days')::interval AS created_at
        FROM generate_series(1,{n}) gs""",
    "categories": """
        SELECT gs AS id,
               'Category ' || gs AS name,
               CASE WHEN gs % 7 = 0 THEN NULL ELSE 1 + (gs % 50) END AS parent_id,
               NOW() - ((random()*600)::int || ' days')::interval AS created_at
        FROM generate_series(1,{n}) gs""",
}


def main():
    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SRC_SCHEMA};")
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {DST_SCHEMA};")
    conn.commit()

    # ── 1. Build source tables (1000 rows each) ─────────────────────────────
    print(f"Creating {len(TABLES)} source tables in {SRC_SCHEMA} ({ROWS} rows each)...")
    for t, select_sql in TABLES.items():
        cur.execute(f'DROP TABLE IF EXISTS {SRC_SCHEMA}."{t}" CASCADE;')
        cur.execute(f'CREATE TABLE {SRC_SCHEMA}."{t}" AS {select_sql.format(n=ROWS)};')
        cur.execute(f'SELECT COUNT(*) FROM {SRC_SCHEMA}."{t}";')
        print(f"  source.{t}: {cur.fetchone()[0]} rows")
    conn.commit()

    # ── 2 + 3. Create dest tables (empty) and ETL load ──────────────────────
    print(f"\nETL load -> {DST_SCHEMA} (simulated Snowflake)...")
    t0 = time.time()
    total_read = 0
    total_written = 0
    per_table = []
    for t in TABLES:
        # empty dest table with identical structure
        cur.execute(f'DROP TABLE IF EXISTS {DST_SCHEMA}."{t}" CASCADE;')
        cur.execute(f'CREATE TABLE {DST_SCHEMA}."{t}" (LIKE {SRC_SCHEMA}."{t}" INCLUDING DEFAULTS);')
        # extract + load
        cur.execute(f'SELECT COUNT(*) FROM {SRC_SCHEMA}."{t}";')
        read = cur.fetchone()[0]
        cur.execute(f'INSERT INTO {DST_SCHEMA}."{t}" SELECT * FROM {SRC_SCHEMA}."{t}";')
        cur.execute(f'SELECT COUNT(*) FROM {DST_SCHEMA}."{t}";')
        written = cur.fetchone()[0]
        total_read += read
        total_written += written
        per_table.append((t, read, written))
        print(f"  {SRC_SCHEMA}.{t} -> {DST_SCHEMA}.{t}: {written} rows")
    conn.commit()
    duration = max(1, round(time.time() - t0))

    # ── 4. Register pipeline + run ──────────────────────────────────────────
    import json
    pipe_name = "pipeline_postgres_to_snowflake"
    dag_id = "pipeline_postgres_to_snowflake"
    source_config = json.dumps({
        "connection": {"host": "postgres", "port": 5432, "database": "orchestrai", "user": "admin"},
        "schema": SRC_SCHEMA,
        "tables": list(TABLES.keys()),
        "sync_mode": "full_refresh",
    })
    dest_config = json.dumps({
        "warehouse": "simulated (PostgreSQL schema)",
        "schema": DST_SCHEMA,
        "tables": list(TABLES.keys()),
    })
    cur.execute("""
        INSERT INTO pipelines (id, name, dag_id, source_type, source_config,
                               dest_type, dest_config, schedule, status, created_at)
        VALUES (gen_random_uuid()::text, %s, %s, 'postgresql', %s::jsonb,
                'snowflake', %s::jsonb, '@daily', 'active', NOW())
        ON CONFLICT (dag_id) DO UPDATE
          SET source_config = EXCLUDED.source_config,
              dest_config   = EXCLUDED.dest_config,
              status        = 'active'
    """, (pipe_name, dag_id, source_config, dest_config))

    cur.execute("""
        INSERT INTO pipeline_runs
          (id, pipeline_name, dag_id, run_id, records_ingested, records_transformed,
           records_loaded, records_failed, status, started_at, completed_at, duration_seconds)
        VALUES (gen_random_uuid()::text, %s, %s, %s, %s, %s, %s, 0, 'success',
                NOW() - (%s || ' seconds')::interval, NOW(), %s)
    """, (pipe_name, dag_id, "etl_" + uuid.uuid4().hex[:8],
          total_read, total_read, total_written, duration, duration))
    conn.commit()

    print("\n" + "=" * 60)
    print(f"Pipeline:  {pipe_name}  (postgresql -> snowflake)")
    print(f"Source:    {SRC_SCHEMA} ({len(TABLES)} tables)")
    print(f"Dest:      {DST_SCHEMA} ({len(TABLES)} tables)  [simulated Snowflake]")
    print(f"Records:   read={total_read}, loaded={total_written}, duration={duration}s")
    print("=" * 60)

    # ── 5. Verify ───────────────────────────────────────────────────────────
    cur.execute(f"""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='{DST_SCHEMA}' ORDER BY table_name
    """)
    dest_tables = [r[0] for r in cur.fetchall()]
    grand = 0
    print(f"\nVerification — {DST_SCHEMA} schema:")
    for t in dest_tables:
        cur.execute(f'SELECT COUNT(*) FROM {DST_SCHEMA}."{t}";')
        c = cur.fetchone()[0]
        grand += c
        print(f"  {t}: {c}")
    print(f"  TOTAL: {grand} rows across {len(dest_tables)} tables")
    conn.close()


if __name__ == "__main__":
    main()
