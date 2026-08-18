"""
Seed the DuckDB warehouse with realistic data for OrchestrAI demo/evaluation.

Tables seeded:
  - nyc_taxi_trips      : 2500 realistic NYC taxi trip records
  - ecommerce_orders    : 1500 e-commerce order records
  - pipeline_metrics_warehouse : 30 days x 4 pipelines = 120 metric rows

Run: python3 /sessions/friendly-fervent-cray/mnt/OrchetraAI/data/seed_warehouse.py
"""
import sys
import os
import random
import uuid
from datetime import datetime, timedelta, date

# Allow imports from the backend package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import duckdb
from pathlib import Path

WAREHOUSE_PATH = Path(__file__).parent / "warehouse.duckdb"
WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)

PARQUET_TAXI   = Path(__file__).parent.parent / "backend" / "sample_data" / "yellow_tripdata_2024-01.parquet"
PARQUET_ORDERS = Path(__file__).parent.parent / "backend" / "sample_data" / "ecommerce_orders.parquet"

con = duckdb.connect(str(WAREHOUSE_PATH))

# ── Ensure tables exist ────────────────────────────────────────────────────────
con.execute("""
    CREATE TABLE IF NOT EXISTS nyc_taxi_trips (
        trip_id VARCHAR PRIMARY KEY,
        pickup_datetime TIMESTAMP,
        dropoff_datetime TIMESTAMP,
        passenger_count INTEGER,
        trip_distance FLOAT,
        fare_amount FLOAT,
        tip_amount FLOAT,
        total_amount FLOAT,
        payment_type VARCHAR,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
con.execute("""
    CREATE TABLE IF NOT EXISTS ecommerce_orders (
        order_id VARCHAR PRIMARY KEY,
        customer_id VARCHAR,
        product_name VARCHAR,
        category VARCHAR,
        quantity INTEGER,
        unit_price FLOAT,
        total_amount FLOAT,
        order_date DATE,
        status VARCHAR,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
con.execute("""
    CREATE TABLE IF NOT EXISTS raw_pipeline_data (
        id VARCHAR PRIMARY KEY,
        pipeline_name VARCHAR NOT NULL,
        source_type VARCHAR NOT NULL,
        records_count INTEGER,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        batch_id VARCHAR,
        workspace_id VARCHAR DEFAULT 'default'
    )
""")
con.execute("""
    CREATE TABLE IF NOT EXISTS pipeline_metrics_warehouse (
        id VARCHAR PRIMARY KEY,
        pipeline_name VARCHAR NOT NULL,
        run_date DATE,
        records_loaded INTEGER,
        records_failed INTEGER,
        duration_seconds FLOAT,
        status VARCHAR,
        loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# ── Helper: try loading from real parquet, fall back to synthetic ──────────────

def load_taxi_trips(n: int = 2500) -> int:
    """Load NYC taxi trips from parquet if available, else generate synthetic."""
    if PARQUET_TAXI.exists():
        try:
            con.execute(f"""
                INSERT OR REPLACE INTO nyc_taxi_trips
                SELECT
                    gen_random_uuid()::VARCHAR       AS trip_id,
                    tpep_pickup_datetime             AS pickup_datetime,
                    tpep_dropoff_datetime            AS dropoff_datetime,
                    CAST(passenger_count AS INTEGER) AS passenger_count,
                    CAST(trip_distance AS FLOAT)     AS trip_distance,
                    CAST(fare_amount AS FLOAT)       AS fare_amount,
                    CAST(tip_amount AS FLOAT)        AS tip_amount,
                    CAST(total_amount AS FLOAT)      AS total_amount,
                    CASE payment_type
                        WHEN 1 THEN 'credit_card'
                        WHEN 2 THEN 'cash'
                        WHEN 3 THEN 'no_charge'
                        WHEN 4 THEN 'dispute'
                        ELSE 'unknown'
                    END                              AS payment_type,
                    CURRENT_TIMESTAMP                AS loaded_at
                FROM read_parquet('{PARQUET_TAXI}')
                LIMIT {n}
            """)
            inserted = con.execute("SELECT COUNT(*) FROM nyc_taxi_trips").fetchone()[0]
            print(f"  [parquet] Loaded {inserted} taxi trips from real parquet file.")
            return inserted
        except Exception as e:
            print(f"  [parquet] Read failed ({e}), falling back to synthetic data.")

    # Synthetic fallback
    payment_types = ["credit_card", "cash", "no_charge", "dispute"]
    base_dt = datetime(2024, 1, 1, 0, 0, 0)
    records = []
    for _ in range(n):
        pickup = base_dt + timedelta(
            days=random.randint(0, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )
        duration_min = random.randint(3, 90)
        dropoff = pickup + timedelta(minutes=duration_min)
        distance = round(random.uniform(0.5, 25.0), 2)
        fare = round(2.50 + distance * 2.50 + duration_min * 0.35, 2)
        tip = round(fare * random.uniform(0, 0.25), 2)
        total = round(fare + tip + random.choice([0, 0, 0, 0.5, 1.0]), 2)
        records.append({
            "trip_id": str(uuid.uuid4()),
            "pickup_datetime": pickup.isoformat(),
            "dropoff_datetime": dropoff.isoformat(),
            "passenger_count": random.randint(1, 6),
            "trip_distance": distance,
            "fare_amount": fare,
            "tip_amount": tip,
            "total_amount": total,
            "payment_type": random.choice(payment_types),
            "loaded_at": datetime.utcnow().isoformat(),
        })

    import pandas as pd
    df = pd.DataFrame(records)
    con.execute("INSERT OR REPLACE INTO nyc_taxi_trips SELECT * FROM df")
    inserted = con.execute("SELECT COUNT(*) FROM nyc_taxi_trips").fetchone()[0]
    print(f"  [synthetic] Generated {inserted} taxi trips.")
    return inserted


def load_ecommerce_orders(n: int = 1500) -> int:
    """Load ecommerce orders from parquet if available, else generate synthetic."""
    if PARQUET_ORDERS.exists():
        try:
            # Inspect columns dynamically
            cols = con.execute(
                f"SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet('{PARQUET_ORDERS}') LIMIT 1)"
            ).fetchall()
            col_names = [c[0].lower() for c in cols]
            print(f"  [parquet] ecommerce_orders columns: {col_names}")

            # Map flexibly to our schema
            def col(candidates, default="NULL"):
                for c in candidates:
                    if c in col_names:
                        return c
                return default

            order_col    = col(["order_id", "id", "orderid"])
            customer_col = col(["customer_id", "customerid", "user_id"])
            product_col  = col(["product_name", "product", "item_name", "name"])
            category_col = col(["category", "product_category", "dept"])
            qty_col      = col(["quantity", "qty", "units"])
            price_col    = col(["unit_price", "price", "amount", "sale_price"])
            total_col    = col(["total_amount", "total", "grand_total"])
            date_col     = col(["order_date", "date", "created_at", "created_date"])
            status_col   = col(["status", "order_status"])

            def expr(c, alias, cast=None, default="'unknown'"):
                if c == "NULL":
                    return f"{default} AS {alias}"
                if cast:
                    return f"TRY_CAST({c} AS {cast}) AS {alias}"
                return f"{c} AS {alias}"

            con.execute(f"""
                INSERT OR REPLACE INTO ecommerce_orders
                SELECT
                    {expr(order_col,    'order_id',    default="gen_random_uuid()::VARCHAR")},
                    {expr(customer_col, 'customer_id', default="'cust_unknown'")},
                    {expr(product_col,  'product_name', default="'Unknown Product'")},
                    {expr(category_col, 'category',    default="'General'")},
                    {expr(qty_col,      'quantity',    cast='INTEGER', default='1')},
                    {expr(price_col,    'unit_price',  cast='FLOAT',   default='0.0')},
                    {expr(total_col,    'total_amount', cast='FLOAT',  default='0.0')},
                    {expr(date_col,     'order_date',  cast='DATE',    default="CURRENT_DATE")},
                    {expr(status_col,   'status',      default="'completed'")},
                    CURRENT_TIMESTAMP AS loaded_at
                FROM read_parquet('{PARQUET_ORDERS}')
                LIMIT {n}
            """)
            inserted = con.execute("SELECT COUNT(*) FROM ecommerce_orders").fetchone()[0]
            print(f"  [parquet] Loaded {inserted} ecommerce orders from real parquet file.")
            return inserted
        except Exception as e:
            print(f"  [parquet] Read failed ({e}), falling back to synthetic data.")

    # Synthetic fallback
    products = [
        ("MacBook Pro 14\"", "Electronics", 1799.99),
        ("iPhone 15 Pro",    "Electronics", 999.99),
        ("Sony WH-1000XM5", "Electronics", 349.99),
        ("Levi's 501 Jeans", "Clothing",    89.99),
        ("Nike Air Max 270", "Footwear",    130.00),
        ("The Lean Startup", "Books",        16.99),
        ("Instant Pot Duo",  "Kitchen",     99.95),
        ("Yoga Mat Pro",     "Sports",       45.00),
        ("Vitamin D3 5000IU","Health",       18.99),
        ("Desk Lamp LED",    "Office",       32.50),
        ("USB-C Hub 7-in-1", "Electronics",  49.99),
        ("Coffee Grinder",   "Kitchen",      65.00),
        ("Running Shoes X",  "Footwear",    110.00),
        ("Smart Watch S10",  "Electronics", 229.99),
        ("Protein Powder",   "Health",       52.99),
    ]
    statuses = ["completed", "completed", "completed", "shipped", "processing", "cancelled"]
    base_date = date(2024, 1, 1)
    records = []
    for _ in range(n):
        product_name, category, unit_price = random.choice(products)
        qty = random.randint(1, 4)
        total = round(unit_price * qty, 2)
        order_date = base_date + timedelta(days=random.randint(0, 179))
        records.append({
            "order_id":     str(uuid.uuid4()),
            "customer_id":  f"cust_{uuid.uuid4().hex[:8]}",
            "product_name": product_name,
            "category":     category,
            "quantity":     qty,
            "unit_price":   unit_price,
            "total_amount": total,
            "order_date":   order_date.isoformat(),
            "status":       random.choice(statuses),
            "loaded_at":    datetime.utcnow().isoformat(),
        })

    import pandas as pd
    df = pd.DataFrame(records)
    con.execute("INSERT OR REPLACE INTO ecommerce_orders SELECT * FROM df")
    inserted = con.execute("SELECT COUNT(*) FROM ecommerce_orders").fetchone()[0]
    print(f"  [synthetic] Generated {inserted} ecommerce orders.")
    return inserted


def seed_pipeline_metrics(days: int = 30) -> int:
    """Seed 30 days of pipeline metrics — one row per pipeline per day."""
    pipelines = [
        ("pipeline_csv_to_snowflake",         "csv",          1200, 1800),
        ("pipeline_postgresql_to_snowflake",   "postgresql",   2000, 3000),
        ("pipeline_rest_api_to_snowflake",     "rest_api",     500,  1200),
        ("pipeline_google_sheets_to_snowflake","google_sheets",150,  600),
    ]
    today = date.today()
    records = []
    for i in range(days):
        run_date = today - timedelta(days=days - 1 - i)
        for pipe_name, _, lo, hi in pipelines:
            loaded  = random.randint(lo, hi)
            failed  = random.randint(0, max(1, int(loaded * 0.01)))
            dur_sec = round(random.uniform(8.0, 120.0), 1)
            status  = "success" if failed < 5 else "warning"
            records.append({
                "id":               str(uuid.uuid4()),
                "pipeline_name":    pipe_name,
                "run_date":         run_date.isoformat(),
                "records_loaded":   loaded,
                "records_failed":   failed,
                "duration_seconds": dur_sec,
                "status":           status,
                "loaded_at":        datetime.utcnow().isoformat(),
            })

    import pandas as pd
    df = pd.DataFrame(records)
    con.execute("INSERT OR REPLACE INTO pipeline_metrics_warehouse SELECT * FROM df")
    inserted = con.execute("SELECT COUNT(*) FROM pipeline_metrics_warehouse").fetchone()[0]
    print(f"  Seeded {inserted} pipeline metric rows ({days} days x {len(pipelines)} pipelines).")
    return inserted


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== OrchestrAI DuckDB Warehouse Seeder ===")
    print(f"Warehouse path: {WAREHOUSE_PATH}\n")

    print("1. Seeding NYC Taxi Trips (2500 records)...")
    taxi_count = load_taxi_trips(2500)

    print("\n2. Seeding Ecommerce Orders (1500 records)...")
    orders_count = load_ecommerce_orders(1500)

    print("\n3. Seeding Pipeline Metrics (30 days x 4 pipelines)...")
    metrics_count = seed_pipeline_metrics(30)

    print("\n=== Seeding Complete ===")
    print(f"  nyc_taxi_trips               : {taxi_count:,} records")
    print(f"  ecommerce_orders             : {orders_count:,} records")
    print(f"  pipeline_metrics_warehouse   : {metrics_count:,} records")

    total = taxi_count + orders_count + metrics_count
    print(f"\n  TOTAL rows in warehouse      : {total:,}")
    print(f"  Warehouse file               : {WAREHOUSE_PATH}")

    con.close()
