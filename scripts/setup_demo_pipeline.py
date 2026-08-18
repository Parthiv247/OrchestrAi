#!/usr/bin/env python3
"""
OrchestrAI — Demo Pipeline Setup
Registers PostgreSQL source + Snowflake (fallback) destination connectors
and creates a Postgres→Snowflake pipeline via the REST API.

Run: python scripts/setup_demo_pipeline.py
"""

import os, sys, json, time
import requests

BASE = os.environ.get("API_BASE", "http://localhost:8000")
HEADERS = {"Content-Type": "application/json", "X-Dev-Mode": "true"}

def api(method, path, body=None, ok=(200, 201)):
    url = f"{BASE}{path}"
    r = getattr(requests, method)(url, json=body, headers=HEADERS, timeout=10)
    if r.status_code not in ok:
        print(f"  ⚠️  {method.upper()} {path} → {r.status_code}: {r.text[:200]}")
        return None
    return r.json()

def wait_for_backend(retries=15):
    for i in range(retries):
        try:
            r = requests.get(f"{BASE}/health", timeout=3)
            if r.status_code in (200, 503):  # 503 = up but deps not ready, still usable
                return True
        except Exception:
            pass
        print(f"  ⏳ Waiting for backend... ({i+1}/{retries})")
        time.sleep(3)
    return False

print("\n🔗 Checking backend connectivity...")
if not wait_for_backend():
    print("  ❌ Backend not reachable at", BASE)
    print("  ℹ️  Start it first: uvicorn backend.main:app --port 8000")
    sys.exit(0)

print("  ✅ Backend is up")

# ── 1. Register PostgreSQL source connector ────────────────────────────────────

print("\n📡 Registering PostgreSQL source connector...")

# Check if already registered
existing = api("get", "/api/connectors/saved", ok=(200,))
if existing:
    names = [c.get("name","") for c in existing] if isinstance(existing, list) else []
    pg_exists = any("Postgres" in n or "postgres" in n.lower() for n in names)
    sf_exists = any("Snowflake" in n or "snowflake" in n.lower() for n in names)
else:
    pg_exists = sf_exists = False

if not pg_exists:
    pg_conn = api("post", "/api/connectors/saved", {
        "name": "PostgreSQL Source (Demo)",
        "db_type": "postgresql",
        "config": {
            "host": "localhost",
            "port": 5432,
            "database": "orchestrai",
            "user": "admin",
            "password": "orchestrai_secret",
        }
    }, ok=(200, 201))

    if pg_conn:
        pg_id = pg_conn.get("id") or pg_conn.get("connection_id")
        print(f"  ✅ PostgreSQL connector registered (id: {pg_id})")
    else:
        print("  ⚠️  Could not register PostgreSQL connector — pipeline creation may fail")
        pg_id = None
else:
    print("  ℹ️  PostgreSQL connector already registered")
    conns = api("get", "/api/connectors/saved", ok=(200,)) or []
    pg_id = next((c["id"] for c in conns if "postgres" in c.get("name","").lower() or
                  "postgres" in c.get("db_type","").lower()), None)

# ── 2. Register Snowflake destination (uses local PG fallback) ─────────────────

print("\n❄️  Registering Snowflake destination connector...")

if not sf_exists:
    sf_conn = api("post", "/api/connectors/saved", {
        "name": "Snowflake Destination (Demo)",
        "db_type": "snowflake",
        "config": {
            "account": "",           # empty → local PG fallback schema
            "user": "demo_user",
            "password": "demo_pass",
            "database": "ORCHESTRAI",
            "warehouse": "COMPUTE_WH",
            "schema": "SNOWFLAKE_DEST",
        }
    }, ok=(200, 201))

    if sf_conn:
        sf_id = sf_conn.get("id") or sf_conn.get("connection_id")
        print(f"  ✅ Snowflake connector registered (id: {sf_id})")
    else:
        print("  ⚠️  Could not register Snowflake connector")
        sf_id = None
else:
    print("  ℹ️  Snowflake connector already registered")
    conns = api("get", "/api/connectors/saved", ok=(200,)) or []
    sf_id = next((c["id"] for c in conns if "snowflake" in c.get("name","").lower() or
                  "snowflake" in c.get("db_type","").lower()), None)

# ── 3. Create Postgres→Snowflake pipeline ─────────────────────────────────────

print("\n🔄 Creating Postgres → Snowflake demo pipeline...")

existing_pipelines = api("get", "/api/pipelines", ok=(200,)) or []
if isinstance(existing_pipelines, dict):
    existing_pipelines = existing_pipelines.get("pipelines", [])

demo_pipeline_exists = any(
    "ecommerce" in p.get("name","").lower() or
    "demo" in p.get("name","").lower()
    for p in existing_pipelines
)

if not demo_pipeline_exists and pg_id and sf_id:
    pipeline = api("post", "/api/pipelines", {
        "name": "E-Commerce Orders → Snowflake",
        "source_connection_id": pg_id,
        "source_table": "ecom_orders",
        "source_query": """
            SELECT o.*, c.company_name, c.segment, c.country
            FROM ecom_orders o
            JOIN ecom_customers c ON o.customer_id = c.customer_id
            WHERE o.status = 'Closed Won'
        """.strip(),
        "dest_connection_id": sf_id,
        "dest_table": "orders_fact",
        "sync_mode": "incremental",
        "cursor_field": "order_date",
    }, ok=(200, 201))

    if pipeline:
        pipeline_id = pipeline.get("id") or pipeline.get("pipeline_id")
        print(f"  ✅ Pipeline created (id: {pipeline_id})")

        # Trigger a run
        print("  🚀 Triggering first pipeline run...")
        run_result = api("post", f"/api/pipelines/{pipeline_id}/run", ok=(200, 201, 202))
        if run_result:
            print("  ✅ Pipeline run triggered!")
        else:
            print("  ⚠️  Could not trigger run (pipeline still registered)")
    else:
        print("  ⚠️  Pipeline creation returned an error")
else:
    if demo_pipeline_exists:
        print("  ℹ️  Demo pipeline already exists")
    else:
        print("  ⚠️  Skipping pipeline — connector IDs not available")
        print("     You can create it manually via the UI at http://localhost:3001/pipelines/new")

# ── 4. Create additional demo pipelines ───────────────────────────────────────

print("\n📊 Creating additional demo pipelines for monitoring view...")

extra_pipelines = [
    ("Customers → Snowflake DW",  "ecom_customers",   "customers_dim"),
    ("Products → Snowflake DW",   "ecom_products",    "products_dim"),
    ("Daily Metrics → Snowflake", "ecom_daily_metrics","daily_metrics_fact"),
]

for name, src_table, dest_table in extra_pipelines:
    if not any(name.lower()[:10] in p.get("name","").lower() for p in existing_pipelines):
        if pg_id and sf_id:
            res = api("post", "/api/pipelines", {
                "name": name,
                "source_connection_id": pg_id,
                "source_table": src_table,
                "dest_connection_id": sf_id,
                "dest_table": dest_table,
                "sync_mode": "full_refresh",
            }, ok=(200, 201))
            if res:
                print(f"  ✅ {name}")

# ── Done ──────────────────────────────────────────────────────────────────────

print("\n" + "═"*55)
print("🎉 DEMO PIPELINES CONFIGURED!")
print("═"*55)
print()
print("  ✅ Connectors registered:")
print("     • PostgreSQL Source (orchestrai DB)")
print("     • Snowflake Destination (local PG fallback)")
print()
print("  ✅ Pipelines created:")
print("     • E-Commerce Orders → Snowflake")
print("     • Customers → Snowflake DW")
print("     • Products → Snowflake DW")
print("     • Daily Metrics → Snowflake")
print()
print("  🖥️  Open the UI:")
print("     Dashboard:   http://localhost:3001/")
print("     Pipelines:   http://localhost:3001/pipelines")
print("     AI Analyst:  http://localhost:3001/analyst")
print("     Connectors:  http://localhost:3001/connectors")
print()
print("  🧪 Demo AI Analyst queries to try:")
print('     "Show total revenue by region for 2025"')
print('     "Which product categories have the highest profit margin?"')
print('     "Top 10 customers by total spend"')
print('     "Monthly revenue trend with growth rate"')
print('     "Average order value by customer segment"')
print('     "Which sales rep closed the most deals?"')
print('     "Revenue breakdown by payment method"')
print('     "Detect any anomalies in daily order volume"')
print("═"*55)
