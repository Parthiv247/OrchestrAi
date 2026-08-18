"""
seed_demo.py — Auto-seeds all demo data on first boot (runs only if DB is empty).

Called from backend/main.py lifespan startup. Safe to call multiple times —
each section checks for existing rows before inserting.

Seeds:
  1. raw.ecommerce_orders   — 500 realistic orders
  2. pipelines table        — 3 demo pipelines
  3. healing_outcomes       — 45 records showing learning curve
  4. system_metrics         — cost savings counter
"""
import os
import random
import uuid
import logging
from datetime import datetime, timedelta

import psycopg2

log = logging.getLogger("orchestrai.seed")

_DB = dict(
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=int(os.getenv("POSTGRES_PORT", 5432)),
    dbname=os.getenv("POSTGRES_DB", "orchestrai"),
    user=os.getenv("POSTGRES_USER", "admin"),
    password=os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
    connect_timeout=10,
)

# ── ecommerce data ─────────────────────────────────────────────────────────────

_PRODUCTS = [
    ("Wireless Headphones", "Electronics", 89.99),
    ("Running Shoes", "Footwear", 129.99),
    ("Coffee Maker", "Kitchen", 74.99),
    ("Yoga Mat", "Sports", 34.99),
    ("Smart Watch", "Electronics", 249.99),
    ("Backpack", "Accessories", 59.99),
    ("Water Bottle", "Sports", 24.99),
    ("Laptop Stand", "Electronics", 49.99),
    ("Desk Lamp", "Home", 39.99),
    ("Sunglasses", "Accessories", 79.99),
    ("Protein Powder", "Health", 44.99),
    ("Phone Case", "Electronics", 19.99),
    ("Notebook", "Stationery", 14.99),
    ("Resistance Bands", "Sports", 29.99),
    ("Air Purifier", "Home", 149.99),
    ("Bluetooth Speaker", "Electronics", 69.99),
    ("Running Watch", "Electronics", 199.99),
    ("Kitchen Knife Set", "Kitchen", 89.99),
    ("Moisturiser", "Beauty", 34.99),
    ("Desk Organiser", "Stationery", 22.99),
]

_STATUSES = ["completed", "completed", "completed", "completed", "pending", "cancelled", "refunded"]
_CITIES = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Pune", "Hyderabad", "Kolkata", "Ahmedabad"]
_SEGMENTS = ["Premium", "Standard", "Economy"]
_PAYMENT = ["credit_card", "debit_card", "upi", "netbanking", "cod"]


def _seed_ecommerce(cur) -> int:
    cur.execute("SELECT COUNT(*) FROM raw.ecommerce_orders")
    count = cur.fetchone()[0]
    if count > 0:
        log.info("raw.ecommerce_orders already has %d rows — skipping seed", count)
        return 0

    now = datetime.utcnow()
    rows = []
    for i in range(500):
        product_name, category, unit_price = random.choice(_PRODUCTS)
        quantity = random.randint(1, 4)
        status = random.choice(_STATUSES)
        city = random.choice(_CITIES)
        days_ago = random.randint(0, 90)
        order_date = now - timedelta(days=days_ago, hours=random.uniform(0, 23))
        total = round(unit_price * quantity, 2)
        customer_id = f"CUST{random.randint(1, 100):04d}"
        segment = random.choice(_SEGMENTS)
        payment = random.choice(_PAYMENT)
        rows.append((
            str(uuid.uuid4()),  # id
            f"ORD{i+1:05d}",   # order_id
            customer_id,
            segment,
            product_name,
            category,
            quantity,
            unit_price,
            total,
            status,
            city,
            payment,
            order_date,
            order_date,
        ))

    cur.executemany(
        """
        INSERT INTO raw.ecommerce_orders
            (id, order_id, customer_id, customer_segment, product_name, category,
             quantity, unit_price, total_amount, status, city, payment_method,
             order_date, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        rows,
    )
    log.info("Seeded %d rows into raw.ecommerce_orders", len(rows))
    return len(rows)


def _ensure_raw_schema(cur):
    """Create raw schema and ecommerce_orders table if they don't exist."""
    cur.execute("CREATE SCHEMA IF NOT EXISTS raw")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS raw.ecommerce_orders (
            id              TEXT PRIMARY KEY,
            order_id        TEXT NOT NULL,
            customer_id     TEXT NOT NULL,
            customer_segment TEXT DEFAULT 'Standard',
            product_name    TEXT NOT NULL,
            category        TEXT,
            quantity        INTEGER NOT NULL DEFAULT 1,
            unit_price      NUMERIC(10,2) NOT NULL,
            total_amount    NUMERIC(10,2) NOT NULL,
            status          TEXT DEFAULT 'pending',
            city            TEXT,
            payment_method  TEXT,
            order_date      TIMESTAMP DEFAULT NOW(),
            created_at      TIMESTAMP DEFAULT NOW()
        )
    """)


# ── pipelines table ─────────────────────────────────────────────────────────────

_DEMO_PIPELINES = [
    {
        "name": "Ecommerce Orders ETL",
        "description": "Ingests ecommerce orders from PostgreSQL source into staging layer with dbt transformations",
        "source_type": "postgresql",
        "destination_type": "postgresql",
        "schedule": "0 */6 * * *",
        "status": "active",
    },
    {
        "name": "Customer Analytics Pipeline",
        "description": "Builds customer segmentation mart from staging layer, detects anomalies with IsolationForest",
        "source_type": "postgresql",
        "destination_type": "postgresql",
        "schedule": "0 0 * * *",
        "status": "active",
    },
    {
        "name": "Revenue Reporting Sync",
        "description": "Generates revenue summary facts and syncs to reporting schema for BI dashboards",
        "source_type": "postgresql",
        "destination_type": "postgresql",
        "schedule": "0 6 * * *",
        "status": "active",
    },
]


def _seed_pipelines(cur) -> int:
    cur.execute("SELECT COUNT(*) FROM pipelines")
    count = cur.fetchone()[0]
    if count > 0:
        log.info("pipelines table already has %d rows — skipping seed", count)
        return 0

    now = datetime.utcnow()
    for p in _DEMO_PIPELINES:
        pid = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO pipelines
                (id, name, description, source_type, destination_type,
                 schedule, status, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
            """,
            (pid, p["name"], p["description"], p["source_type"],
             p["destination_type"], p["schedule"], p["status"], now, now),
        )
    log.info("Seeded %d demo pipelines", len(_DEMO_PIPELINES))
    return len(_DEMO_PIPELINES)


# ── pipeline_runs (real run history — IsolationForest trains on this) ─────────

_PIPELINE_NAMES_RUN = [
    "Ecommerce Orders ETL",
    "Customer Analytics Pipeline",
    "Revenue Reporting Sync",
]

# Failure injection types — mirror what the ML classifier detects
_FAILURE_TYPES = ["ZERO_LOAD", "SCHEMA_DRIFT", "THROUGHPUT_DROP", "DATA_QUALITY_FAIL", "CONNECTOR_TIMEOUT"]


def _seed_pipeline_runs(cur) -> int:
    cur.execute("SELECT COUNT(*) FROM pipeline_runs")
    count = cur.fetchone()[0]
    if count > 0:
        log.info("pipeline_runs already has %d rows — skipping seed", count)
        return 0

    now = datetime.utcnow()
    rows = []

    # Seed 80 runs across 30 days — 70 healthy, 10 with injected failures
    for i in range(80):
        days_ago = random.randint(0, 30)
        started = now - timedelta(days=days_ago, hours=random.uniform(0, 23))
        pipeline_name = random.choice(_PIPELINE_NAMES_RUN)

        # 10 runs are "failed" (injected anomalies for training)
        is_failure = (i % 8 == 0)

        if is_failure:
            # Anomaly pattern: low records, high duration, errors present
            records_in  = random.randint(0, 50)          # near-zero load
            records_out = int(records_in * 0.3)
            errors      = random.randint(1, 20)
            duration    = random.randint(600, 2400)       # unusually long
            status      = "failed"
            error_msg   = random.choice([
                "Connection timeout after 30s",
                "Schema mismatch: column 'unit_price' not found",
                "Record count dropped 95% vs previous run",
                "NULL rate exceeded threshold (42% nulls in customer_id)",
                "Source table returned 0 rows",
            ])
        else:
            # Normal healthy run
            records_in  = random.randint(400, 600)
            records_out = int(records_in * random.uniform(0.95, 1.0))
            errors      = 0
            duration    = random.randint(80, 180)
            status      = "success"
            error_msg   = None

        null_rate   = round(random.uniform(0, 0.02) if not is_failure else random.uniform(0.15, 0.45), 4)
        completed   = started + timedelta(seconds=duration)

        rows.append((
            str(uuid.uuid4()),
            pipeline_name,
            f"dag_{pipeline_name.lower().replace(' ','_')}",
            str(uuid.uuid4()),
            records_in,
            records_out,
            records_out,
            errors,
            status,
            error_msg,
            started,
            completed,
            duration,
        ))

    cur.executemany(
        """
        INSERT INTO pipeline_runs
            (id, pipeline_name, dag_id, run_id,
             records_ingested, records_transformed, records_loaded, records_failed,
             status, error_message, started_at, completed_at, duration_seconds)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        rows,
    )
    log.info("Seeded %d pipeline_runs rows (10 with injected failures)", len(rows))
    return len(rows)


# ── healing outcomes (learning curve) ────────────────────────────────────────

def _seed_healing_outcomes() -> int:
    """Seed healing_outcomes using its own DB connection."""
    try:
        conn = psycopg2.connect(**_DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM healing_outcomes WHERE approved_by = 'seed_script'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        if count > 0:
            log.info("healing_outcomes seed already present (%d rows) — skipping", count)
            return 0
    except Exception:
        pass  # table may not exist yet — seed_outcomes handles it

    try:
        from .seed_outcomes import seed
        seed(clear_existing=False)
        return 45
    except Exception as e:
        log.warning("seed_outcomes failed: %s", e)
        return 0


# ── system_metrics ────────────────────────────────────────────────────────────

def _seed_system_metrics(cur) -> None:
    cur.execute(
        """
        INSERT INTO system_metrics (id, metric_name, metric_value, updated_at)
        VALUES (gen_random_uuid()::text, 'total_cost_saved', 0, NOW())
        ON CONFLICT (metric_name) DO NOTHING
        """
    )


# ── main entry point ──────────────────────────────────────────────────────────

def seed_if_empty() -> None:
    """
    Called from main.py lifespan. Seeds demo data only if each section is empty.
    Safe to call on every restart.
    """
    try:
        conn = psycopg2.connect(**_DB)
    except Exception as e:
        log.warning("seed_if_empty: cannot connect to DB (%s) — skipping", e)
        return

    try:
        cur = conn.cursor()

        # 1. Ensure raw schema + table
        _ensure_raw_schema(cur)
        conn.commit()

        # 2. Ecommerce orders
        _seed_ecommerce(cur)
        conn.commit()

        # 3. Demo pipelines
        try:
            _seed_pipelines(cur)
            conn.commit()
        except Exception as e:
            conn.rollback()
            log.warning("Pipeline seed failed (table may not exist yet): %s", e)

        # 4. Pipeline runs — real run history for IsolationForest training
        try:
            _seed_pipeline_runs(cur)
            conn.commit()
        except Exception as e:
            conn.rollback()
            log.warning("Pipeline runs seed failed: %s", e)

        # 4. System metrics
        try:
            _seed_system_metrics(cur)
            conn.commit()
        except Exception as e:
            conn.rollback()
            log.warning("System metrics seed failed: %s", e)

        cur.close()
    except Exception as e:
        log.warning("seed_if_empty encountered error: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # Healing outcomes uses its own connection
    _seed_healing_outcomes(None)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    seed_if_empty()
    print("Seeding complete.")
