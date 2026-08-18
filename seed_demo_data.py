"""
OrchestrAI — Viva Demo Seed Script
Inserts ~5000 records across all key tables for a complete live demo.
Run once before the viva:  python seed_demo_data.py
"""
import os, uuid, random, json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

load_dotenv()

DB = {
    "host":     os.getenv("POSTGRES_HOST", "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname":   os.getenv("POSTGRES_DB", "orchestrai"),
    "user":     os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}

random.seed(2024)

def uid(): return str(uuid.uuid4())
def dt(days_ago=0, hours=0):
    return datetime.utcnow() - timedelta(days=days_ago, hours=hours)
def fmt(d): return d.strftime("%Y-%m-%d %H:%M:%S")

conn = psycopg2.connect(**DB)
cur  = conn.cursor()
print("✓ Connected to PostgreSQL:", DB["dbname"])

# ══════════════════════════════════════════════════════════════════════════════
# 1. DEMO SOURCE TABLES  (for PostgreSQL → Snowflake connector pipeline)
# ══════════════════════════════════════════════════════════════════════════════

cur.execute("""
DROP TABLE IF EXISTS fact_orders CASCADE;
DROP TABLE IF EXISTS dim_customers CASCADE;
DROP TABLE IF EXISTS raw_products CASCADE;
DROP TABLE IF EXISTS raw_orders CASCADE;
DROP TABLE IF EXISTS raw_customers CASCADE;
""")

# raw_customers
cur.execute("""
CREATE TABLE raw_customers (
  customer_id   SERIAL PRIMARY KEY,
  first_name    VARCHAR(80),
  last_name     VARCHAR(80),
  email         VARCHAR(150) UNIQUE,
  phone         VARCHAR(30),
  city          VARCHAR(80),
  country       VARCHAR(60),
  segment       VARCHAR(40),
  signup_date   DATE,
  is_active     BOOLEAN DEFAULT TRUE
);
""")

FIRST = ["Aarav","Priya","Rohan","Sneha","Vikram","Ananya","Karan","Meera","Arjun","Divya",
         "Rahul","Pooja","Nikhil","Shreya","Aditya","Kavya","Siddharth","Riya","Mohit","Nisha",
         "James","Maria","Chris","Anna","David","Emma","Lucas","Sophia","Noah","Olivia"]
LAST  = ["Patel","Sharma","Kumar","Singh","Gupta","Mehta","Shah","Joshi","Reddy","Rao",
         "Verma","Nair","Iyer","Pillai","Smith","Johnson","Williams","Brown","Davis","Miller"]
CITIES    = ["Mumbai","Bengaluru","Delhi","Hyderabad","Pune","Chennai","New York","London","Singapore","Dubai"]
COUNTRIES = ["India","India","India","India","USA","UK","Singapore","UAE","Germany","Australia"]
SEGMENTS  = ["Enterprise","SMB","Startup","Individual","Agency"]

customers = []
used_emails = set()
for i in range(500):
    fn  = random.choice(FIRST)
    ln  = random.choice(LAST)
    em  = f"{fn.lower()}.{ln.lower()}{i}@demo.com"
    used_emails.add(em)
    ci  = random.randint(0,9)
    customers.append((
        fn, ln, em,
        f"+91-{random.randint(7000,9999)}-{random.randint(100000,999999)}",
        CITIES[ci], COUNTRIES[ci],
        random.choice(SEGMENTS),
        (datetime(2021,1,1) + timedelta(days=random.randint(0,1000))).date(),
        random.random() > 0.08
    ))

execute_values(cur, """
  INSERT INTO raw_customers
    (first_name,last_name,email,phone,city,country,segment,signup_date,is_active)
  VALUES %s
""", customers)
print(f"✓ raw_customers: {len(customers)} rows")

# raw_products
cur.execute("""
CREATE TABLE raw_products (
  product_id   SERIAL PRIMARY KEY,
  product_name VARCHAR(150),
  category     VARCHAR(80),
  unit_price   NUMERIC(10,2),
  cost_price   NUMERIC(10,2),
  supplier     VARCHAR(100),
  in_stock     BOOLEAN DEFAULT TRUE
);
""")

PRODUCTS = [
    ("Data Pipeline Starter","Software",299.00,89.00,"Hevo"),
    ("Data Pipeline Pro","Software",799.00,200.00,"Hevo"),
    ("Analytics Dashboard","Software",499.00,120.00,"Hevo"),
    ("ML Model Monitor","AI Tools",999.00,300.00,"Hevo"),
    ("Schema Registry","Data Infra",199.00,60.00,"Hevo"),
    ("Cost Optimizer Plugin","Software",399.00,100.00,"Hevo"),
    ("dbt Accelerator","Data Infra",699.00,180.00,"Hevo"),
    ("Lineage Explorer","Data Infra",349.00,90.00,"Hevo"),
    ("Data Quality Suite","Software",549.00,140.00,"Hevo"),
    ("AI Analyst Module","AI Tools",1199.00,350.00,"Hevo"),
    ("Snowflake Connector","Connector",149.00,40.00,"Partner"),
    ("Postgres Connector","Connector",99.00,25.00,"Partner"),
    ("Kafka Connector","Connector",199.00,55.00,"Partner"),
    ("S3 Connector","Connector",79.00,20.00,"Partner"),
    ("BigQuery Connector","Connector",149.00,40.00,"Partner"),
]
execute_values(cur, """
  INSERT INTO raw_products (product_name,category,unit_price,cost_price,supplier,in_stock)
  VALUES %s
""", PRODUCTS)
print(f"✓ raw_products: {len(PRODUCTS)} rows")

# raw_orders  (2000 records — backbone of AI Analyst + dbt demo)
cur.execute("""
CREATE TABLE raw_orders (
  order_id        SERIAL PRIMARY KEY,
  customer_id     INT REFERENCES raw_customers(customer_id),
  product_id      INT,
  order_date      DATE,
  quantity        INT,
  unit_price      NUMERIC(10,2),
  discount_pct    NUMERIC(5,2) DEFAULT 0,
  total_amount    NUMERIC(12,2),
  status          VARCHAR(30),
  region          VARCHAR(40),
  payment_method  VARCHAR(40),
  channel         VARCHAR(40)
);
""")

REGIONS  = ["South Asia","North America","Europe","Southeast Asia","Middle East","APAC"]
METHODS  = ["Credit Card","Bank Transfer","UPI","PayPal","Invoice","Stripe"]
CHANNELS = ["Web","Mobile","Sales Rep","Partner","API"]
STATUSES_O = ["completed","completed","completed","pending","refunded","cancelled"]

orders = []
for _ in range(2000):
    cust_id  = random.randint(1,500)
    prod_idx = random.randint(0,len(PRODUCTS)-1)
    qty      = random.randint(1, 10)
    price    = float(PRODUCTS[prod_idx][2])
    disc     = round(random.choice([0,0,0,5,10,15,20]),2)
    total    = round(qty * price * (1 - disc/100), 2)
    # seasonal pattern: more orders in Nov-Dec
    base_date = datetime(2023,1,1) + timedelta(days=random.randint(0,547))
    if base_date.month in [11,12]: base_date -= timedelta(days=0)  # keep as-is
    orders.append((
        cust_id, prod_idx+1,
        base_date.date(),
        qty, price, disc, total,
        random.choice(STATUSES_O),
        random.choice(REGIONS),
        random.choice(METHODS),
        random.choice(CHANNELS),
    ))

execute_values(cur, """
  INSERT INTO raw_orders
    (customer_id,product_id,order_date,quantity,unit_price,
     discount_pct,total_amount,status,region,payment_method,channel)
  VALUES %s
""", orders)
print(f"✓ raw_orders: {len(orders)} rows")

# dbt-generated tables (simulate dbt mart output)
cur.execute("""
CREATE TABLE dim_customers AS
SELECT
  c.customer_id,
  c.first_name || ' ' || c.last_name AS full_name,
  c.email, c.city, c.country, c.segment,
  c.signup_date,
  COUNT(o.order_id)        AS total_orders,
  SUM(o.total_amount)      AS lifetime_value,
  MAX(o.order_date)        AS last_order_date,
  c.is_active
FROM raw_customers c
LEFT JOIN raw_orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.first_name, c.last_name,
         c.email, c.city, c.country, c.segment, c.signup_date, c.is_active;
""")

cur.execute("""
CREATE TABLE fact_orders AS
SELECT
  o.order_id,
  o.customer_id,
  c.full_name    AS customer_name,
  c.segment      AS customer_segment,
  p.product_name,
  p.category     AS product_category,
  o.order_date,
  EXTRACT(YEAR  FROM o.order_date) AS order_year,
  EXTRACT(MONTH FROM o.order_date) AS order_month,
  EXTRACT(QUARTER FROM o.order_date) AS order_quarter,
  o.quantity,
  o.unit_price,
  o.discount_pct,
  o.total_amount,
  o.total_amount - (p.cost_price * o.quantity) AS gross_profit,
  o.status,
  o.region,
  o.payment_method,
  o.channel
FROM raw_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
JOIN raw_products  p ON o.product_id  = p.product_id;
""")
print("✓ dim_customers + fact_orders (dbt-style marts created)")

# ══════════════════════════════════════════════════════════════════════════════
# 2. PIPELINE_RUNS  (500 records — fills the Dashboard)
# ══════════════════════════════════════════════════════════════════════════════
PIPELINES = [
    "payments_raw","orders_agg","users_dim","inventory_sync",
    "marketing_events","returns_pipeline","finance_gl","product_catalog",
]
STATUSES_P = ["success","success","success","success","failed","running","healing"]

pipeline_runs = []
for i in range(500):
    name   = random.choice(PIPELINES)
    status = random.choice(STATUSES_P)
    started = dt(days_ago=random.randint(0,90), hours=random.randint(0,23))
    dur     = random.randint(30, 900)
    records = random.randint(500, 50000)
    failed  = random.randint(0,50) if status == "failed" else 0
    pipeline_runs.append((
        uid(), name,
        f"dag_{name}_{i}",
        f"run_{uid()[:8]}",
        records, int(records*0.98), int(records*0.97), failed,
        status,
        "Schema drift detected: column renamed" if status=="failed" else None,
        fmt(started),
        fmt(started + timedelta(seconds=dur)) if status!="running" else None,
        dur if status!="running" else None,
    ))

execute_values(cur, """
  INSERT INTO pipeline_runs
    (id,pipeline_name,dag_id,run_id,
     records_ingested,records_transformed,records_loaded,records_failed,
     status,error_message,started_at,completed_at,duration_seconds)
  VALUES %s
""", pipeline_runs)
print(f"✓ pipeline_runs: {len(pipeline_runs)} rows")

# ══════════════════════════════════════════════════════════════════════════════
# 3. PIPELINE_METRICS  (400 records)
# ══════════════════════════════════════════════════════════════════════════════
metrics_rows = []
METRIC_NAMES = [
    "throughput_rps","error_rate_pct","latency_p99_ms",
    "memory_mb","cpu_pct","queue_depth","schema_version",
]
for i in range(400):
    metrics_rows.append((
        uid(),
        random.choice(PIPELINES),
        random.choice(METRIC_NAMES),
        round(random.uniform(0.01, 1000), 4),
        fmt(dt(days_ago=random.randint(0,30), hours=random.randint(0,23))),
    ))
execute_values(cur, """
  INSERT INTO pipeline_metrics (id,pipeline_name,metric_name,metric_value,recorded_at)
  VALUES %s
""", metrics_rows)
print(f"✓ pipeline_metrics: {len(metrics_rows)} rows")

# ══════════════════════════════════════════════════════════════════════════════
# 4. DBT_RUNS  (20 records — fills the dbt page)
# ══════════════════════════════════════════════════════════════════════════════
dbt_rows = []
for i in range(20):
    models = random.randint(4,12)
    passed = random.randint(models-2, models)
    failed = models - passed
    dbt_rows.append((
        uid(),
        random.choice(["orchestrai_admin","system","ci_pipeline"]),
        models, passed, failed,
        random.randint(passed*2, passed*5),
        random.randint(0,3),
        json.dumps(["fact_orders","dim_customers","stg_payments","mart_revenue"]),
        "Running dbt build --select +fact_orders+\n01:14:02  Found 4 models, 12 tests\n01:14:08  Completed successfully",
        fmt(dt(days_ago=random.randint(0,14), hours=random.randint(0,23))),
    ))
execute_values(cur, """
  INSERT INTO dbt_runs
    (id,triggered_by,models_generated,models_succeeded,models_failed,
     tests_passed,tests_failed,mart_tables_created,run_output,created_at)
  VALUES %s
""", dbt_rows)
print(f"✓ dbt_runs: {len(dbt_rows)} rows")

# ══════════════════════════════════════════════════════════════════════════════
# 5. INCIDENTS — including 1 PENDING_APPROVAL for schema drift demo
# ══════════════════════════════════════════════════════════════════════════════
incidents = []

# ── The STAR of the demo: pending approval, schema drift ────────────────────
star_id = uid()
star_sandbox = {
    "checks_passed": 12, "checks_failed": 0,
    "details": [
        {"check":"Row Count Minimum","result":"PASS","severity":"ABORT"},
        {"check":"Primary Key Uniqueness","result":"PASS","severity":"ABORT"},
        {"check":"Data Type Consistency","result":"PASS","severity":"ABORT"},
        {"check":"Execution Time Limit","result":"PASS","severity":"ABORT"},
        {"check":"Null Rate per Column","result":"PASS","severity":"FAIL"},
        {"check":"New Null Columns","result":"PASS","severity":"FAIL"},
        {"check":"Foreign Key Integrity","result":"PASS","severity":"FAIL"},
        {"check":"Schema Fingerprint Match","result":"PASS","severity":"FAIL"},
        {"check":"No All-Null Columns","result":"PASS","severity":"FAIL"},
        {"check":"Row Count Stability","result":"PASS","severity":"WARN"},
        {"check":"Numeric Mean Drift","result":"PASS","severity":"WARN"},
        {"check":"Categorical Value Set","result":"PASS","severity":"WARN"},
    ],
    "execution_time_sec": 3.4,
    "docker_image": "orchestrai-sandbox:latest",
    "sample_size": 1000,
}
star_lineage = {
    "source": "payments_raw",
    "affected_models": ["stg_payments","fact_orders","mart_revenue"],
    "impact_count": 3,
}
incidents.append((
    star_id, None,
    "payments_raw",
    f"run_{uid()[:8]}",
    "schema_drift",
    json.dumps({"column_renamed": {"old": "amount_usd", "new": "amount"}, "detected_at": fmt(dt(hours=2)), "confidence": 0.97}),
    json.dumps(star_lineage),
    "Column 'amount_usd' was renamed to 'amount' in the payments_raw table at Hevo source. This breaks 3 downstream dbt models: stg_payments, fact_orders, mart_revenue.",
    0.97,
    """-- Fix Writer Agent: Schema Migration Fix
-- Incident: INC-2024-047  |  Pipeline: payments_raw
-- Root Cause: Column rename amount_usd -> amount

-- Step 1: Add new column with correct name
ALTER TABLE payments_raw ADD COLUMN IF NOT EXISTS amount_usd NUMERIC(12,2);

-- Step 2: Backfill from renamed column
UPDATE payments_raw SET amount_usd = amount WHERE amount_usd IS NULL;

-- Step 3: Update dbt source reference
-- models/staging/stg_payments.sql: replace ref('amount') with ref('amount_usd')

-- Step 4: Refresh downstream models
-- dbt run --select stg_payments+ --full-refresh""",
    "sql",
    json.dumps(star_sandbox),
    12, 0, 0.97,
    "pending", None, "admin@orchestrai.com", None,
    False, None,
    "pending_approval",
    False, None,
    fmt(dt(hours=2)), None,
))

# ── Past resolved incidents ──────────────────────────────────────────────────
ANOMALY_TYPES = ["schema_drift","volume_spike","null_rate_increase","type_mismatch","pk_violation"]
for i in range(19):
    atype  = random.choice(ANOMALY_TYPES)
    status = random.choice(["deployed","deployed","deployed","closed"])
    inc_id = uid()
    sb = {"checks_passed":12,"checks_failed":0,"execution_time_sec":round(random.uniform(2,8),1)}
    incidents.append((
        inc_id, None,
        random.choice(PIPELINES),
        f"run_{uid()[:8]}",
        atype,
        json.dumps({"confidence": round(random.uniform(0.82,0.99),2)}),
        json.dumps({"source": random.choice(PIPELINES), "affected_models": random.randint(1,4)}),
        f"Anomaly detected: {atype.replace('_',' ')} in upstream table. LangGraph diagnosis complete.",
        round(random.uniform(0.80,0.99),2),
        "-- AI-generated fix\nALTER TABLE source_table ADD COLUMN fixed_col VARCHAR(255);",
        "sql",
        json.dumps(sb),
        12, 0, round(random.uniform(0.85,0.99),2),
        "approved", uid(), "admin@orchestrai.com", "admin",
        True, json.dumps({"result":"success","rows_affected":random.randint(100,5000)}),
        status,
        True, None,
        fmt(dt(days_ago=random.randint(1,30))),
        fmt(dt(days_ago=random.randint(0,1))),
    ))

execute_values(cur, """
  INSERT INTO incidents
    (id,tenant_id,pipeline_name,run_id,
     anomaly_type,anomaly_details,lineage_graph,
     root_cause,root_cause_confidence,
     fix_code,fix_language,
     sandbox_results,tests_passed,tests_failed,confidence_score,
     approval_status,approval_token,approval_email,approved_by,
     deployed,deployment_result,
     status,sandbox_passed,error,
     created_at,resolved_at)
  VALUES %s
""", incidents)
print(f"✓ incidents: {len(incidents)} rows  (1 pending_approval for schema drift demo)")

# ══════════════════════════════════════════════════════════════════════════════
# 6. QUERY_OPTIMIZATIONS  (30 records)
# ══════════════════════════════════════════════════════════════════════════════
bad_sqls = [
    ("SELECT * FROM fact_orders WHERE order_date > '2023-01-01'",
     "SELECT order_id,total_amount,region FROM fact_orders WHERE order_date > '2023-01-01'",
     ["SELECT *","missing partition filter"],
     45.2,18.1),
    ("SELECT a.*,b.* FROM fact_orders a CROSS JOIN raw_customers b",
     "SELECT a.order_id,b.full_name FROM fact_orders a JOIN dim_customers b ON a.customer_id=b.customer_id",
     ["CROSS JOIN","cartesian product"],
     312.5,8.4),
    ("SELECT * FROM fact_orders ORDER BY order_date",
     "SELECT order_id,total_amount FROM fact_orders WHERE order_date>=CURRENT_DATE-30 ORDER BY order_date",
     ["full table scan","missing WHERE clause"],
     89.0,12.3),
]
qo_rows = []
for i in range(30):
    sql_idx = i % len(bad_sqls)
    orig,opt,changes,oc,nc = bad_sqls[sql_idx]
    save = round((oc-nc)/oc*100, 1)
    qo_rows.append((
        uid(), None, orig, opt,
        json.dumps(changes), oc, nc, save,
        round((oc-nc)*0.0028,4),
        random.randint(4200,8500), random.randint(800,2100),
        fmt(dt(days_ago=random.randint(0,20))),
    ))
execute_values(cur, """
  INSERT INTO query_optimizations
    (id,connection_id,original_sql,optimized_sql,changes_made,
     original_cost,optimized_cost,savings_percent,dollar_savings,
     execution_time_before_ms,execution_time_after_ms,created_at)
  VALUES %s
""", qo_rows)
print(f"✓ query_optimizations: {len(qo_rows)} rows")

# ══════════════════════════════════════════════════════════════════════════════
# 7. INSIGHTS  (pre-seeded AI insights for the dashboard)
# ══════════════════════════════════════════════════════════════════════════════
insights_rows = [
    (uid(), None,
     "Revenue 34% Higher in Q4 vs Q3",
     "Fact orders show a strong Q4 seasonality pattern. November and December account for 41% of annual revenue. Consider pre-scaling warehouse resources in October.",
     "opportunity", "quarterly_revenue", "30d", "fact_orders",
     "SELECT order_quarter, SUM(total_amount) FROM fact_orders GROUP BY order_quarter ORDER BY 1",
     fmt(dt(hours=1))),
    (uid(), None,
     "Enterprise Segment: 68% of Revenue from 12% of Customers",
     "Enterprise customers generate disproportionate revenue. Churning any Enterprise account has 5.6× the revenue impact of an SMB account.",
     "anomaly", "segment_revenue_share", "7d", "dim_customers",
     "SELECT segment, COUNT(*), SUM(lifetime_value) FROM dim_customers GROUP BY segment ORDER BY 3 DESC",
     fmt(dt(hours=2))),
    (uid(), None,
     "Credit Card Payments Declining: -18% vs Last Quarter",
     "Payment method shift from Credit Card to UPI (+31%) detected. Bank Transfer stable. No revenue impact but affects cash flow timing.",
     "warning", "payment_method_trend", "30d", "fact_orders",
     "SELECT payment_method, COUNT(*), SUM(total_amount) FROM fact_orders WHERE order_year=2023 GROUP BY payment_method",
     fmt(dt(hours=3))),
    (uid(), None,
     "South Asia Region Drives 43% of Orders",
     "Regional concentration risk: South Asia is dominant. North America growing at +22% MoM but still 2nd. Diversification opportunity in APAC.",
     "opportunity", "regional_distribution", "7d", "fact_orders",
     "SELECT region, COUNT(*) AS orders, SUM(total_amount) AS revenue FROM fact_orders GROUP BY region ORDER BY 2 DESC",
     fmt(dt(hours=4))),
    (uid(), None,
     "3 Snowflake Queries Consuming 78% of Credit Budget",
     "CROSS JOIN on fact_orders + raw_customers identified. Rewrite to INNER JOIN estimated to save 72% credits. Cost Optimizer fix ready.",
     "anomaly", "query_cost_outlier", "24h", "query_optimizations",
     "SELECT original_sql, original_cost, savings_percent FROM query_optimizations ORDER BY savings_percent DESC LIMIT 5",
     fmt(dt(hours=1))),
]
execute_values(cur, """
  INSERT INTO insights
    (id,connection_id,title,insight,severity,metric,time_window,table_name,supporting_sql,generated_at)
  VALUES %s
""", insights_rows)
print(f"✓ insights: {len(insights_rows)} AI insights pre-seeded")

# ══════════════════════════════════════════════════════════════════════════════
# 8. QUERY_HISTORY  (pre-filled analyst questions so history shows on reload)
# ══════════════════════════════════════════════════════════════════════════════
qh_rows = [
    (uid(),None,None,
     "Show me total revenue by region",
     "SELECT region, SUM(total_amount) AS total_revenue FROM fact_orders GROUP BY region ORDER BY total_revenue DESC",
     None, 6, 412, "bar", 1, fmt(dt(hours=6))),
    (uid(),None,None,
     "Which product categories have the highest sales?",
     "SELECT product_category, COUNT(*) AS orders, SUM(total_amount) AS revenue FROM fact_orders GROUP BY product_category ORDER BY revenue DESC",
     None, 10, 389, "bar", 1, fmt(dt(hours=5))),
    (uid(),None,None,
     "Show monthly revenue trend for 2023",
     "SELECT order_month, SUM(total_amount) AS monthly_revenue FROM fact_orders WHERE order_year=2023 GROUP BY order_month ORDER BY order_month",
     None, 12, 445, "line", 1, fmt(dt(hours=4))),
    (uid(),None,None,
     "Who are the top 10 customers by lifetime value?",
     "SELECT full_name, segment, lifetime_value FROM dim_customers ORDER BY lifetime_value DESC LIMIT 10",
     None, 10, 378, "bar", 1, fmt(dt(hours=3))),
    (uid(),None,None,
     "What is the pipeline failure rate by pipeline name?",
     "SELECT pipeline_name, COUNT(*) AS total_runs, SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failures FROM pipeline_runs GROUP BY pipeline_name ORDER BY failures DESC",
     None, 8, 290, "bar", 1, fmt(dt(hours=2))),
]
execute_values(cur, """
  INSERT INTO query_history
    (id,tenant_id,user_id,question,generated_sql,optimized_sql,
     rows_returned,execution_time_ms,chart_type,feedback,created_at)
  VALUES %s
""", qh_rows)
print(f"✓ query_history: {len(qh_rows)} pre-filled questions")

conn.commit()
cur.close()
conn.close()

total = len(customers)+len(PRODUCTS)+len(orders)+len(pipeline_runs)+len(metrics_rows)+len(dbt_rows)+len(incidents)+len(qo_rows)+len(insights_rows)+len(qh_rows)
print(f"\n{'='*60}")
print(f"✓ SEED COMPLETE — {total:,} records inserted")
print(f"{'='*60}")
print(f"  raw_customers       : 500")
print(f"  raw_products        : {len(PRODUCTS)}")
print(f"  raw_orders          : 2,000")
print(f"  dim_customers (dbt) : 500")
print(f"  fact_orders   (dbt) : 2,000")
print(f"  pipeline_runs       : 500")
print(f"  pipeline_metrics    : 400")
print(f"  dbt_runs            : 20")
print(f"  incidents           : 20  (1 pending approval)")
print(f"  query_optimizations : 30")
print(f"  insights            : 5")
print(f"  query_history       : 5")
print(f"{'='*60}")
print(f"\nPostgreSQL Connector credentials for the UI:")
print(f"  Host     : localhost")
print(f"  Port     : 5432")
print(f"  Database : orchestrai")
print(f"  Username : admin")
print(f"  Password : orchestrai_secret")
