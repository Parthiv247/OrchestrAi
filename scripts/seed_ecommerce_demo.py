#!/usr/bin/env python3
"""
OrchestrAI — Real E-Commerce Demo Data Seeder
Loads 10,000+ realistic orders/customers/products into PostgreSQL
AND seeds the OrchestrAI pipeline-monitoring tables.

Run: python scripts/seed_ecommerce_demo.py
"""

import os, sys, uuid, random, json
from datetime import datetime, timedelta, date
from decimal import Decimal

import psycopg2
import psycopg2.extras

# ── Connection ──────────────────────────────────────────────────────────────
DSN = {
    "host": os.environ.get("POSTGRES_HOST", "localhost"),
    "port": int(os.environ.get("POSTGRES_PORT", 5432)),
    "dbname": os.environ.get("POSTGRES_DB", "orchestrai"),
    "user": os.environ.get("POSTGRES_USER", "admin"),
    "password": os.environ.get("POSTGRES_PASSWORD", "orchestrai_secret"),
}

try:
    conn = psycopg2.connect(**DSN)
    conn.autocommit = False
    cur = conn.cursor()
    print("✅ Connected to PostgreSQL")
except Exception as e:
    print(f"❌ Cannot connect to PostgreSQL: {e}")
    sys.exit(1)

# ── Helpers ──────────────────────────────────────────────────────────────────
def randdate(days_back=730, days_forward=0):
    d = datetime.utcnow() - timedelta(days=random.randint(days_forward, days_back))
    return d.replace(microsecond=0)

rng = random.Random(42)  # deterministic seed for repeatable demo

# ── DATA DEFINITIONS ─────────────────────────────────────────────────────────

REGIONS = ["North America", "Europe", "Asia Pacific", "South America", "Middle East & Africa"]
REGION_WEIGHTS = [0.38, 0.28, 0.22, 0.07, 0.05]

COUNTRIES = {
    "North America": ["United States", "Canada", "Mexico"],
    "Europe": ["United Kingdom", "Germany", "France", "Netherlands", "Spain"],
    "Asia Pacific": ["Japan", "Australia", "Singapore", "India", "South Korea"],
    "South America": ["Brazil", "Argentina", "Chile"],
    "Middle East & Africa": ["UAE", "South Africa", "Saudi Arabia"],
}

SEGMENTS = ["Enterprise", "SMB", "Startup", "Government", "Education"]
SEG_WEIGHTS = [0.25, 0.40, 0.20, 0.10, 0.05]

PRODUCTS = [
    # (name, category, subcategory, base_price, cost_ratio)
    ("DataSync Pro License",    "Software",  "Analytics",    2400.0, 0.15),
    ("DataSync Team License",   "Software",  "Analytics",     899.0, 0.15),
    ("DataSync Starter",        "Software",  "Analytics",     299.0, 0.15),
    ("Pipeline Monitor Annual", "Software",  "Monitoring",   1800.0, 0.20),
    ("Pipeline Monitor Monthly","Software",  "Monitoring",    189.0, 0.20),
    ("AI Analyst Add-On",       "Software",  "AI/ML",        1200.0, 0.18),
    ("NL-SQL Query Pack",       "Software",  "AI/ML",         599.0, 0.18),
    ("Cost Optimizer Module",   "Software",  "Optimization",  750.0, 0.22),
    ("dbt Integration Pack",    "Software",  "Integration",   450.0, 0.25),
    ("Connector Bundle (10x)",  "Software",  "Integration",   950.0, 0.25),
    ("Enterprise Support SLA",  "Services",  "Support",      3600.0, 0.40),
    ("Onboarding Package",      "Services",  "Consulting",   2000.0, 0.50),
    ("Data Migration Service",  "Services",  "Consulting",   5000.0, 0.55),
    ("Custom Dashboard Dev",    "Services",  "Development",  4500.0, 0.60),
    ("Training Workshop",       "Services",  "Training",      800.0, 0.35),
    ("Server Node (Small)",     "Hardware",  "Infrastructure",3200.0, 0.65),
    ("Server Node (Large)",     "Hardware",  "Infrastructure",8500.0, 0.65),
    ("Storage Expansion 10TB",  "Hardware",  "Storage",      2100.0, 0.60),
    ("Network Appliance",       "Hardware",  "Networking",   1750.0, 0.62),
    ("Backup Device",           "Hardware",  "Storage",      1100.0, 0.58),
]

SALES_REPS = [
    "Aarav Sharma", "Priya Patel", "Michael Chen", "Sarah Williams",
    "James O'Brien", "Fatima Al-Hassan", "Lucas Silva", "Emma Müller",
    "Hiroshi Tanaka", "Ananya Krishnan",
]

CHANNELS = ["Direct Sales", "Partner", "Web/Self-Serve", "Reseller", "Marketplace"]
CHAN_WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08]

PAYMENT_METHODS = ["Bank Transfer", "Credit Card", "PO/Invoice", "Wire Transfer", "ACH"]

STATUS_FLOW = {
    "Closed Won": 0.62,
    "Closed Lost": 0.18,
    "In Progress": 0.12,
    "Pending": 0.08,
}

FIRST_NAMES = ["Aarav","Priya","James","Sarah","Michael","Emma","Lucas","Fatima",
               "Hiroshi","Ananya","Olivia","Noah","Liam","Sofia","Aiden","Mia",
               "Ethan","Isabella","Mason","Charlotte","Logan","Amelia","Jacob",
               "Evelyn","William","Abigail","Alexander","Emily","Daniel","Harper"]
LAST_NAMES  = ["Sharma","Patel","Williams","Chen","O'Brien","Müller","Silva",
               "Al-Hassan","Tanaka","Krishnan","Johnson","Brown","Davis","Wilson",
               "Anderson","Taylor","Martinez","Thomas","Garcia","Robinson","Clark",
               "Rodriguez","Lewis","Lee","Walker","Hall","Allen","Young","King","Wright"]
COMPANY_SUFF = ["Inc.", "Ltd.", "Corp.", "Solutions", "Technologies", "Systems",
                "Consulting", "Group", "Partners", "Enterprises"]
COMPANY_WORDS= ["Acme","Apex","Nexus","Vantage","Pinnacle","Horizon","Summit",
                "Global","Prime","Synergy","Core","Logic","Bridge","Vertex","Quantum",
                "DataFlow","CloudFirst","InfoStream","PipelineX","Orbis"]

def random_company():
    return f"{rng.choice(COMPANY_WORDS)} {rng.choice(COMPANY_SUFF)}"

def random_name():
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"

def random_email(name, company):
    safe = name.lower().replace("'","").replace(" ",".")
    dom = company.lower().split()[0].replace("'","").replace(".","")
    tlds = ["com","io","net","co"]
    return f"{safe}@{dom}.{rng.choice(tlds)}"

# ── 1. CREATE BUSINESS TABLES ─────────────────────────────────────────────────

print("\n📦 Creating e-commerce business tables...")

CREATE_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS ecom_customers (
    customer_id     TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    company_name    TEXT NOT NULL,
    contact_name    TEXT NOT NULL,
    email           TEXT UNIQUE NOT NULL,
    phone           TEXT,
    segment         TEXT,
    region          TEXT,
    country         TEXT,
    city            TEXT,
    annual_revenue  NUMERIC(14,2),
    employee_count  INT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ecom_products (
    product_id      TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    sku             TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL,
    subcategory     TEXT,
    unit_price      NUMERIC(10,2) NOT NULL,
    unit_cost       NUMERIC(10,2) NOT NULL,
    currency        TEXT DEFAULT 'USD',
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ecom_orders (
    order_id        TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    order_number    TEXT UNIQUE NOT NULL,
    customer_id     TEXT REFERENCES ecom_customers(customer_id),
    order_date      TIMESTAMP NOT NULL,
    ship_date       TIMESTAMP,
    status          TEXT NOT NULL,
    payment_method  TEXT,
    sales_rep       TEXT,
    channel         TEXT,
    region          TEXT,
    country         TEXT,
    discount_pct    NUMERIC(5,2) DEFAULT 0,
    subtotal        NUMERIC(14,2),
    discount_amount NUMERIC(14,2),
    total_amount    NUMERIC(14,2),
    profit          NUMERIC(14,2),
    currency        TEXT DEFAULT 'USD',
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ecom_order_items (
    item_id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    order_id        TEXT REFERENCES ecom_orders(order_id),
    product_id      TEXT REFERENCES ecom_products(product_id),
    quantity        INT NOT NULL,
    unit_price      NUMERIC(10,2) NOT NULL,
    unit_cost       NUMERIC(10,2) NOT NULL,
    discount_pct    NUMERIC(5,2) DEFAULT 0,
    line_total      NUMERIC(14,2) NOT NULL,
    line_profit     NUMERIC(14,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS ecom_daily_metrics (
    metric_date     DATE NOT NULL,
    region          TEXT NOT NULL,
    orders_count    INT,
    revenue         NUMERIC(14,2),
    profit          NUMERIC(14,2),
    new_customers   INT,
    avg_order_value NUMERIC(10,2),
    PRIMARY KEY (metric_date, region)
);
"""

for stmt in CREATE_SQL.split(";"):
    stmt = stmt.strip()
    if stmt:
        cur.execute(stmt)
conn.commit()
print("✅ Tables created")

# ── 2. SEED PRODUCTS ──────────────────────────────────────────────────────────

print("🛍️  Seeding products...")
cur.execute("SELECT COUNT(*) FROM ecom_products")
if cur.fetchone()[0] == 0:
    product_ids = []
    for i, (name, cat, sub, price, cost_r) in enumerate(PRODUCTS):
        pid = str(uuid.uuid4())
        sku = f"SKU-{cat[:3].upper()}-{i+1:04d}"
        cur.execute("""
            INSERT INTO ecom_products (product_id, sku, name, category, subcategory, unit_price, unit_cost)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (sku) DO NOTHING
        """, (pid, sku, name, cat, sub, price, round(price * cost_r, 2)))
        product_ids.append(pid)
    conn.commit()
    print(f"  ✅ {len(PRODUCTS)} products inserted")
else:
    print("  ℹ️  Products already seeded")

# Reload product_ids from DB
cur.execute("SELECT product_id, unit_price, unit_cost, category FROM ecom_products ORDER BY created_at")
db_products = cur.fetchall()  # (pid, price, cost, category)

# ── 3. SEED CUSTOMERS (2,000) ─────────────────────────────────────────────────

print("👥 Seeding 2,000 customers...")
cur.execute("SELECT COUNT(*) FROM ecom_customers")
existing_customers = cur.fetchone()[0]
if existing_customers < 100:
    customer_ids = []
    for i in range(2000):
        region = rng.choices(REGIONS, weights=REGION_WEIGHTS)[0]
        country = rng.choice(COUNTRIES[region])
        segment = rng.choices(SEGMENTS, weights=SEG_WEIGHTS)[0]
        company = random_company()
        name = random_name()
        email = random_email(name, company)
        # Make revenue realistic by segment
        if segment == "Enterprise":
            revenue = round(rng.uniform(10_000_000, 500_000_000), 2)
            employees = rng.randint(500, 50000)
        elif segment == "Government":
            revenue = round(rng.uniform(5_000_000, 100_000_000), 2)
            employees = rng.randint(200, 20000)
        elif segment == "SMB":
            revenue = round(rng.uniform(500_000, 10_000_000), 2)
            employees = rng.randint(10, 500)
        elif segment == "Startup":
            revenue = round(rng.uniform(100_000, 5_000_000), 2)
            employees = rng.randint(5, 100)
        else:  # Education
            revenue = round(rng.uniform(1_000_000, 50_000_000), 2)
            employees = rng.randint(50, 5000)

        cities = {
            "United States": ["New York", "San Francisco", "Austin", "Chicago", "Seattle"],
            "United Kingdom": ["London", "Manchester", "Edinburgh"],
            "Germany": ["Berlin", "Munich", "Hamburg"],
            "India": ["Bangalore", "Mumbai", "Hyderabad"],
            "Japan": ["Tokyo", "Osaka", "Yokohama"],
        }
        city = rng.choice(cities.get(country, ["Capital City"]))
        cid = str(uuid.uuid4())
        try:
            cur.execute("""
                INSERT INTO ecom_customers
                  (customer_id, company_name, contact_name, email, phone, segment,
                   region, country, city, annual_revenue, employee_count)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (email) DO NOTHING
            """, (cid, company, name,
                  f"{email.split('@')[0]}_{i}@{email.split('@')[1]}",  # make unique
                  f"+1-{rng.randint(200,999)}-{rng.randint(100,999)}-{rng.randint(1000,9999)}",
                  segment, region, country, city, revenue, employees))
            customer_ids.append(cid)
        except Exception:
            pass

        if (i + 1) % 500 == 0:
            conn.commit()
            print(f"  ... {i+1}/2000 customers")
    conn.commit()
    print(f"  ✅ 2,000 customers seeded")
else:
    print(f"  ℹ️  {existing_customers} customers already seeded")

# Reload customer IDs
cur.execute("SELECT customer_id, region, country, segment FROM ecom_customers")
db_customers = cur.fetchall()  # (cid, region, country, segment)

# ── 4. SEED ORDERS (10,000) ───────────────────────────────────────────────────

print("📋 Seeding 10,000 orders...")
cur.execute("SELECT COUNT(*) FROM ecom_orders")
existing_orders = cur.fetchone()[0]

if existing_orders < 100:
    order_ids = []
    item_batch = []
    order_batch = []
    order_num = 10001

    for i in range(10000):
        cid, c_region, c_country, c_segment = rng.choice(db_customers)
        pid, p_price, p_cost, p_cat = rng.choice(db_products)
        status = rng.choices(list(STATUS_FLOW.keys()), weights=list(STATUS_FLOW.values()))[0]
        channel = rng.choices(CHANNELS, weights=CHAN_WEIGHTS)[0]
        sales_rep = rng.choice(SALES_REPS)
        payment = rng.choice(PAYMENT_METHODS)

        # Order date — spread across 2 years with a slight recent uptick
        days_back = int(rng.betavariate(2, 5) * 730)  # weighted toward recent
        order_date = datetime.utcnow() - timedelta(days=days_back)

        # Ship date
        if status == "Closed Won":
            ship_date = order_date + timedelta(days=rng.randint(1, 14))
        else:
            ship_date = None

        # Quantity (enterprise buys more)
        qty_max = {"Enterprise": 20, "Government": 15, "SMB": 8, "Startup": 5, "Education": 10}
        qty = rng.randint(1, qty_max.get(c_segment, 5))

        # Discount — enterprise gets more
        disc_ranges = {"Enterprise": (10, 30), "Government": (5, 20), "SMB": (0, 15),
                       "Startup": (0, 10), "Education": (5, 25)}
        disc_low, disc_high = disc_ranges.get(c_segment, (0, 15))
        disc_pct = round(rng.uniform(disc_low, disc_high), 1)

        subtotal = round(float(p_price) * qty, 2)
        disc_amount = round(subtotal * disc_pct / 100, 2)
        total = round(subtotal - disc_amount, 2)
        profit = round((float(p_price) - float(p_cost)) * qty * (1 - disc_pct / 100), 2)

        oid = str(uuid.uuid4())
        order_num_str = f"ORD-{order_num:06d}"
        order_num += 1

        order_batch.append((
            oid, order_num_str, cid, order_date, ship_date, status,
            payment, sales_rep, channel, c_region, c_country,
            disc_pct, subtotal, disc_amount, total, profit
        ))

        # Line item
        line_total = round(float(p_price) * qty * (1 - disc_pct / 100), 2)
        line_profit = round((float(p_price) - float(p_cost)) * qty * (1 - disc_pct / 100), 2)
        item_batch.append((
            str(uuid.uuid4()), oid, pid, qty,
            float(p_price), float(p_cost), disc_pct,
            line_total, line_profit
        ))

        # Flush every 500
        if len(order_batch) >= 500:
            psycopg2.extras.execute_batch(cur, """
                INSERT INTO ecom_orders
                  (order_id, order_number, customer_id, order_date, ship_date, status,
                   payment_method, sales_rep, channel, region, country,
                   discount_pct, subtotal, discount_amount, total_amount, profit)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (order_number) DO NOTHING
            """, order_batch)
            psycopg2.extras.execute_batch(cur, """
                INSERT INTO ecom_order_items
                  (item_id, order_id, product_id, quantity, unit_price, unit_cost,
                   discount_pct, line_total, line_profit)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, item_batch)
            conn.commit()
            order_ids.extend([r[0] for r in order_batch])
            order_batch.clear()
            item_batch.clear()
            print(f"  ... {i+1}/10000 orders")

    # Flush remainder
    if order_batch:
        psycopg2.extras.execute_batch(cur, """
            INSERT INTO ecom_orders
              (order_id, order_number, customer_id, order_date, ship_date, status,
               payment_method, sales_rep, channel, region, country,
               discount_pct, subtotal, discount_amount, total_amount, profit)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (order_number) DO NOTHING
        """, order_batch)
        psycopg2.extras.execute_batch(cur, """
            INSERT INTO ecom_order_items
              (item_id, order_id, product_id, quantity, unit_price, unit_cost,
               discount_pct, line_total, line_profit)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, item_batch)
        conn.commit()

    print(f"  ✅ 10,000 orders + line items seeded")
else:
    print(f"  ℹ️  {existing_orders} orders already seeded")

# ── 5. AGGREGATE DAILY METRICS ────────────────────────────────────────────────

print("📊 Computing daily metrics (for AI Analyst charts)...")
cur.execute("SELECT COUNT(*) FROM ecom_daily_metrics")
if cur.fetchone()[0] < 50:
    cur.execute("""
        INSERT INTO ecom_daily_metrics (metric_date, region, orders_count, revenue, profit, new_customers, avg_order_value)
        SELECT
            order_date::date                    AS metric_date,
            region,
            COUNT(*)                            AS orders_count,
            ROUND(SUM(total_amount)::numeric,2) AS revenue,
            ROUND(SUM(profit)::numeric,2)       AS profit,
            COUNT(DISTINCT customer_id)         AS new_customers,
            ROUND(AVG(total_amount)::numeric,2) AS avg_order_value
        FROM ecom_orders
        WHERE status = 'Closed Won'
        GROUP BY 1, 2
        ON CONFLICT (metric_date, region) DO UPDATE SET
            orders_count    = EXCLUDED.orders_count,
            revenue         = EXCLUDED.revenue,
            profit          = EXCLUDED.profit,
            new_customers   = EXCLUDED.new_customers,
            avg_order_value = EXCLUDED.avg_order_value
    """)
    conn.commit()
    print("  ✅ Daily metrics aggregated")

# ── 6. SEED ORCHESTRAI PIPELINE RUNS (90-day history) ────────────────────────

print("\n🔄 Seeding OrchestrAI pipeline monitoring history...")
cur.execute("SELECT COUNT(*) FROM pipelines")
if cur.fetchone()[0] == 0:
    pipelines_to_seed = [
        ("pg_to_snowflake_orders",     "pg_to_snowflake_orders",     "postgresql"),
        ("pg_to_snowflake_customers",  "pg_to_snowflake_customers",  "postgresql"),
        ("pg_to_snowflake_products",   "pg_to_snowflake_products",   "postgresql"),
        ("pg_to_snowflake_metrics",    "pg_to_snowflake_metrics",    "postgresql"),
    ]
    pipeline_map = {}  # dag_id -> db id
    for name, dag_id, source_type in pipelines_to_seed:
        pid = str(uuid.uuid4())
        pipeline_map[dag_id] = pid
        cur.execute("""
            INSERT INTO pipelines (id, name, dag_id, source_type, status, created_at)
            VALUES (%s, %s, %s, %s, 'active', NOW())
            ON CONFLICT (dag_id) DO NOTHING
        """, (pid, name, dag_id, source_type))
    conn.commit()

    # 90 days of runs
    now = datetime.utcnow()
    run_batch = []
    record_volumes = {
        "pg_to_snowflake_orders":    (300, 50),
        "pg_to_snowflake_customers": (80,  15),
        "pg_to_snowflake_products":  (20,  3),
        "pg_to_snowflake_metrics":   (150, 30),
    }

    for dag_id, pid in pipeline_map.items():
        avg_r, std_r = record_volumes.get(dag_id, (100, 20))
        for day in range(90, 0, -1):
            runs_today = rng.randint(1, 4)
            for run_num in range(runs_today):
                started = now - timedelta(days=day, hours=rng.randint(0,23), minutes=rng.randint(0,59))
                duration = rng.randint(15, 180)
                completed = started + timedelta(seconds=duration)

                # Inject some failures for the healing demo
                if day <= 14 and rng.random() < 0.08:
                    ingested = max(0, int(rng.gauss(avg_r, std_r)))
                    loaded, failed = 0, ingested
                    status = "failed"
                    error = rng.choice([
                        "Connection timeout after 30s — postgres source unreachable",
                        "Schema drift detected: column 'profit' missing in destination",
                        "Zero rows extracted — source table may have been truncated",
                        "SSL handshake failed: certificate verification error",
                        "Destination quota exceeded: Snowflake warehouse suspended",
                    ])
                else:
                    ingested = max(0, int(rng.gauss(avg_r, std_r)))
                    failed = rng.randint(0, max(1, ingested // 100))
                    loaded = ingested - failed
                    status = "success"
                    error = None

                run_batch.append((
                    str(uuid.uuid4()), dag_id, dag_id,
                    f"run_{uuid.uuid4().hex[:8]}",
                    ingested, ingested, loaded, failed,
                    status, error, started, completed, duration
                ))

        if len(run_batch) >= 200:
            psycopg2.extras.execute_batch(cur, """
                INSERT INTO pipeline_runs
                  (id, pipeline_name, dag_id, run_id, records_ingested,
                   records_transformed, records_loaded, records_failed,
                   status, error_message, started_at, completed_at, duration_seconds)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, run_batch)
            conn.commit()
            run_batch.clear()

    if run_batch:
        psycopg2.extras.execute_batch(cur, """
            INSERT INTO pipeline_runs
              (id, pipeline_name, dag_id, run_id, records_ingested,
               records_transformed, records_loaded, records_failed,
               status, error_message, started_at, completed_at, duration_seconds)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, run_batch)
        conn.commit()

    print("  ✅ 90-day pipeline run history seeded")
else:
    print("  ℹ️  Pipeline runs already seeded")

# ── 7. SEED HEALING INCIDENTS ─────────────────────────────────────────────────

print("🚨 Seeding healing incidents...")
cur.execute("SELECT COUNT(*) FROM incidents")
if cur.fetchone()[0] < 5:
    anomaly_types = ["ZERO_LOAD", "ROW_COUNT_DROP", "ML_ANOMALY", "NULL_SPIKE", "CONSECUTIVE_FAILURES"]
    pipelines_for_incidents = [
        "pg_to_snowflake_orders", "pg_to_snowflake_customers",
        "pg_to_snowflake_products", "pg_to_snowflake_metrics"
    ]
    statuses = ["resolved", "resolved", "resolved", "pending", "pending"]  # mostly resolved for demo

    now = datetime.utcnow()
    for i in range(18):
        created = now - timedelta(days=rng.randint(0, 14), hours=rng.randint(0, 23))
        resolved = created + timedelta(minutes=rng.randint(3, 45)) if rng.random() > 0.3 else None
        atype = rng.choice(anomaly_types)
        pipeline = rng.choice(pipelines_for_incidents)
        approval = "approved" if resolved else "pending"

        cur.execute("""
            INSERT INTO incidents
              (id, pipeline_name, anomaly_type, root_cause,
               status, approval_status, resolved_at, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            str(uuid.uuid4()), pipeline, atype,
            rng.choice([
                "Source schema changed — new column added without migration",
                "Network partition between regions caused connection timeout",
                "Destination warehouse throttled during peak load",
                "Upstream API rate limit hit — exponential backoff triggered",
                "CDC offset lag detected — source and destination out of sync",
                "Memory pressure on source host — extraction paused",
            ]),
            "closed" if resolved else "open",
            approval, resolved, created
        ))

    conn.commit()
    print("  ✅ 18 healing incidents seeded")
else:
    print("  ℹ️  Incidents already seeded")

# ── 8. SUMMARY ────────────────────────────────────────────────────────────────

cur.execute("SELECT COUNT(*) FROM ecom_customers")
n_customers = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM ecom_orders")
n_orders = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM ecom_order_items")
n_items = cur.fetchone()[0]
cur.execute("SELECT ROUND(SUM(total_amount)::numeric,2) FROM ecom_orders WHERE status='Closed Won'")
total_rev = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM pipeline_runs")
n_runs = cur.fetchone()[0]

cur.close()
conn.close()

print("\n" + "═"*55)
print("🎉 DEMO DATA READY!")
print("═"*55)
print(f"  Customers      : {n_customers:,}")
print(f"  Orders         : {n_orders:,}")
print(f"  Order Items    : {n_items:,}")
print(f"  Total Revenue  : ${total_rev:,} (Closed Won)")
print(f"  Pipeline Runs  : {n_runs:,}")
print("═"*55)
print("\n✅ PostgreSQL is ready for the demo!")
print("   Demo AI Analyst queries you can run:")
print('   • "Show total revenue by region for the last 12 months"')
print('   • "Which product categories are most profitable?"')
print('   • "Top 10 customers by lifetime value"')
print('   • "Monthly revenue trend with month-over-month growth"')
print('   • "Which sales reps have the highest win rate?"')
