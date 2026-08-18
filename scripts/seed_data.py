"""
Seed realistic demo data into all OrchestrAI tables so the dashboard looks live.
Corrected for the actual schema + Phase 4 LearningAgent API.
"""
import sys
import uuid
import random
from datetime import datetime, timedelta

sys.path.insert(0, '/Users/parthivpatel/OrchetraAI')

import psycopg2

DB_DSN = 'postgresql://admin:orchestrai_secret@localhost:5432/orchestrai'

conn = psycopg2.connect(DB_DSN)
cur = conn.cursor()
now = datetime.utcnow()

cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — PIPELINE RUNS (90 days of history)
# ═══════════════════════════════════════════════════════════════════════════════
pipelines = [
    ('pipeline_rest_api_to_snowflake', 'pipeline_rest_api_to_snowflake', 'rest_api'),
    ('pipeline_postgresql_to_snowflake', 'pipeline_postgresql_to_snowflake', 'postgresql'),
    ('pipeline_google_sheets_to_snowflake', 'pipeline_google_sheets_to_snowflake', 'google_sheets'),
    ('pipeline_csv_to_snowflake', 'pipeline_csv_to_snowflake', 'csv'),
]
for name, dag_id, source_type in pipelines:
    cur.execute("""
        INSERT INTO pipelines (id, name, dag_id, source_type, status, created_at)
        VALUES (gen_random_uuid()::text, %s, %s, %s, 'active', NOW())
        ON CONFLICT (dag_id) DO NOTHING
    """, (name, dag_id, source_type))

base_records = {
    'pipeline_rest_api_to_snowflake': (85, 12),
    'pipeline_postgresql_to_snowflake': (4200, 300),
    'pipeline_google_sheets_to_snowflake': (150, 20),
    'pipeline_csv_to_snowflake': (48000, 5000),
}

run_count = 0
for name, dag_id, source_type in pipelines:
    avg, std = base_records[name]
    for day in range(90, 0, -1):
        runs_today = random.randint(1, 3)
        for run_num in range(runs_today):
            started = now - timedelta(days=day, hours=random.randint(0, 23), minutes=random.randint(0, 59))
            duration = random.randint(20, 120)
            completed = started + timedelta(seconds=duration)

            if day <= 7 and run_num == 0 and random.random() < 0.15:
                ingested = int(random.gauss(avg, std))
                loaded = 0
                failed = ingested
                status = 'failed'
                error = random.choice([
                    'API endpoint returned 503 Service Unavailable',
                    'Connection timeout after 30s — source unreachable',
                    'Schema mismatch: column "timestamp" not found in destination',
                    'Zero rows extracted — source may have changed format',
                ])
            else:
                ingested = max(0, int(random.gauss(avg, std)))
                failed = random.randint(0, max(1, int(ingested * 0.01)))
                loaded = ingested - failed
                status = 'success'
                error = None

            cur.execute("""
                INSERT INTO pipeline_runs
                  (id, pipeline_name, dag_id, run_id, records_ingested,
                   records_transformed, records_loaded, records_failed,
                   status, error_message, started_at, completed_at, duration_seconds)
                VALUES (gen_random_uuid()::text, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, dag_id, f'run_{uuid.uuid4().hex[:8]}',
                  ingested, ingested, loaded, failed, status, error,
                  started, completed, duration))
            run_count += 1

            cur.execute("""
                INSERT INTO pipeline_metrics (id, pipeline_name, metric_name, metric_value, recorded_at)
                VALUES (gen_random_uuid()::text, %s, 'records_loaded', %s, %s),
                       (gen_random_uuid()::text, %s, 'duration_seconds', %s, %s),
                       (gen_random_uuid()::text, %s, 'records_failed', %s, %s)
            """, (name, loaded, completed, name, duration, completed, name, failed, completed))

conn.commit()
print(f"✅ Pipeline runs seeded: {run_count}")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — INCIDENTS (8 realistic incidents)
# ═══════════════════════════════════════════════════════════════════════════════
incidents = [
    {'pipeline': 'pipeline_rest_api_to_snowflake', 'anomaly_type': 'zero_load',
     'anomaly_details': '{"expected": 85, "actual": 0, "drop_pct": 100}',
     'root_cause': 'REST API changed response format — "results" key renamed to "data", causing extraction to return empty DataFrame',
     'confidence': 0.94,
     'fix_code': 'def apply_fix(df):\n    import pandas as pd\n    if df.empty:\n        return df\n    rename_map = {c: c.lower().replace(" ", "_") for c in df.columns}\n    df = df.rename(columns=rename_map)\n    return df.dropna(how="all")\n\ndef verify(before, after):\n    return len(after) >= len(before) * 0.9',
     'tests_passed': 11, 'tests_failed': 1, 'confidence_score': 0.917,
     'approval_status': 'deployed', 'deployed': True, 'days_ago': 45},
    {'pipeline': 'pipeline_postgresql_to_snowflake', 'anomaly_type': 'row_count_drop',
     'anomaly_details': '{"expected": 4180, "actual": 980, "drop_pct": 76.6}',
     'root_cause': 'PostgreSQL source query missing date filter — incremental cursor was reset to epoch causing full re-scan to hit query timeout at 30s',
     'confidence': 0.88,
     'fix_code': 'def apply_fix(df):\n    import pandas as pd\n    from datetime import datetime, timedelta\n    if "updated_at" in df.columns:\n        df["updated_at"] = pd.to_datetime(df["updated_at"])\n        cutoff = datetime.utcnow() - timedelta(days=1)\n        df = df[df["updated_at"] >= cutoff]\n    return df\n\ndef verify(before, after):\n    return len(after) > 0',
     'tests_passed': 12, 'tests_failed': 0, 'confidence_score': 1.0,
     'approval_status': 'deployed', 'deployed': True, 'days_ago': 30},
    {'pipeline': 'pipeline_csv_to_snowflake', 'anomaly_type': 'ml_anomaly',
     'anomaly_details': '{"isolation_forest_score": -0.31, "threshold": -0.10}',
     'root_cause': 'NYC Taxi parquet file schema changed in January 2024 release — new column "airport_fee" added, causing downstream type inference to fail silently',
     'confidence': 0.79,
     'fix_code': 'def apply_fix(df):\n    import pandas as pd\n    expected_cols = ["VendorID","tpep_pickup_datetime","tpep_dropoff_datetime",\n                     "passenger_count","trip_distance","fare_amount","tip_amount","total_amount"]\n    existing = [c for c in expected_cols if c in df.columns]\n    df = df[existing].copy()\n    df["trip_distance"] = pd.to_numeric(df["trip_distance"], errors="coerce").fillna(0)\n    df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0)\n    return df[df["total_amount"] > 0]\n\ndef verify(before, after):\n    return len(after) > len(before) * 0.5',
     'tests_passed': 10, 'tests_failed': 2, 'confidence_score': 0.833,
     'approval_status': 'deployed', 'deployed': True, 'days_ago': 22},
    {'pipeline': 'pipeline_google_sheets_to_snowflake', 'anomaly_type': 'consecutive_failures',
     'anomaly_details': '{"failed_runs": 2, "last_errors": ["403 Forbidden", "403 Forbidden"]}',
     'root_cause': 'Google Sheets API credentials expired — service account token rotation policy set to 30 days, token not renewed',
     'confidence': 0.97,
     'fix_code': 'def apply_fix(df):\n    import pandas as pd\n    df = df.copy()\n    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]\n    return df.dropna(how="all")\n\ndef verify(before, after):\n    return not after.empty',
     'tests_passed': 11, 'tests_failed': 1, 'confidence_score': 0.917,
     'approval_status': 'rejected', 'deployed': False, 'days_ago': 18},
    {'pipeline': 'pipeline_rest_api_to_snowflake', 'anomaly_type': 'pipeline_delay',
     'anomaly_details': '{"avg_duration_s": 42, "actual_duration_s": 187, "slowdown_factor": 4.5}',
     'root_cause': 'Open-Meteo API rate limit hit — free tier allows 10,000 calls/day, pipeline now paginates with 500ms sleep between calls',
     'confidence': 0.85,
     'fix_code': 'def apply_fix(df):\n    import pandas as pd\n    if "time" in df.columns:\n        df = df.drop_duplicates(subset=["time"])\n        df = df.sort_values("time").reset_index(drop=True)\n    return df\n\ndef verify(before, after):\n    return len(after) >= len(before) * 0.95',
     'tests_passed': 12, 'tests_failed': 0, 'confidence_score': 1.0,
     'approval_status': 'deployed', 'deployed': True, 'days_ago': 12},
    {'pipeline': 'pipeline_postgresql_to_snowflake', 'anomaly_type': 'zero_load',
     'anomaly_details': '{"expected": 4200, "actual": 0}',
     'root_cause': 'Source PostgreSQL connection pool exhausted — 20 concurrent DAG tasks opened connections without releasing, hitting max_connections=20 limit',
     'confidence': 0.91,
     'fix_code': 'def apply_fix(df):\n    import pandas as pd\n    if df.empty:\n        return df\n    numeric_cols = df.select_dtypes(include=["object"]).columns\n    for col in numeric_cols:\n        try:\n            df[col] = pd.to_numeric(df[col])\n        except Exception:\n            pass\n    return df\n\ndef verify(before, after):\n    return len(after) > 0',
     'tests_passed': 11, 'tests_failed': 1, 'confidence_score': 0.917,
     'approval_status': 'pending', 'deployed': False, 'days_ago': 3},
    {'pipeline': 'pipeline_csv_to_snowflake', 'anomaly_type': 'row_count_drop',
     'anomaly_details': '{"expected": 47800, "actual": 12300, "drop_pct": 74.3}',
     'root_cause': 'S3 parquet file partitioned by month — pipeline reading only first partition due to glob pattern mismatch after bucket reorganization',
     'confidence': 0.82,
     'fix_code': 'def apply_fix(df):\n    import pandas as pd\n    if "tpep_pickup_datetime" in df.columns:\n        df["tpep_pickup_datetime"] = pd.to_datetime(df["tpep_pickup_datetime"], errors="coerce")\n    if "trip_distance" in df.columns:\n        df["trip_distance"] = pd.to_numeric(df["trip_distance"], errors="coerce").fillna(0)\n    return df[df["trip_distance"] >= 0]\n\ndef verify(before, after):\n    return len(after) > len(before) * 0.8',
     'tests_passed': 10, 'tests_failed': 2, 'confidence_score': 0.833,
     'approval_status': 'pending', 'deployed': False, 'days_ago': 1},
    {'pipeline': 'pipeline_google_sheets_to_snowflake', 'anomaly_type': 'ml_anomaly',
     'anomaly_details': '{"isolation_forest_score": -0.24}',
     'root_cause': 'Google Sheet manually edited — 47 rows deleted by a team member, Isolation Forest flagged the 68% drop as anomalous',
     'confidence': 0.73,
     'fix_code': 'def apply_fix(df):\n    import pandas as pd\n    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]\n    for col in df.select_dtypes(include=["object"]).columns:\n        df[col] = df[col].str.strip()\n    return df.drop_duplicates()\n\ndef verify(before, after):\n    return len(after) > 0',
     'tests_passed': 9, 'tests_failed': 3, 'confidence_score': 0.75,
     'approval_status': 'pending', 'deployed': False, 'days_ago': 0},
]

for inc in incidents:
    created = now - timedelta(days=inc['days_ago'], hours=random.randint(1, 6))
    resolved = created + timedelta(hours=random.randint(1, 4)) if inc['deployed'] else None
    token = uuid.uuid4().hex if inc['approval_status'] == 'pending' else None
    cur.execute("""
        INSERT INTO incidents
          (id, pipeline_name, anomaly_type, anomaly_details, root_cause,
           root_cause_confidence, fix_code, fix_language, tests_passed, tests_failed,
           confidence_score, approval_status, approval_token, deployed,
           created_at, resolved_at)
        VALUES (gen_random_uuid()::text, %s, %s, %s::jsonb, %s, %s, %s, 'python', %s, %s, %s, %s, %s, %s, %s, %s)
    """, (inc['pipeline'], inc['anomaly_type'], inc['anomaly_details'],
          inc['root_cause'], inc['confidence'], inc['fix_code'],
          inc['tests_passed'], inc['tests_failed'], inc['confidence_score'],
          inc['approval_status'], token, inc['deployed'], created, resolved))

conn.commit()
print(f"✅ Incidents seeded: {len(incidents)}")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — QUERY HISTORY + COST SAVINGS
# ═══════════════════════════════════════════════════════════════════════════════
sample_queries = [
    ("How many records were loaded today?",
     "SELECT COUNT(*) FROM pipeline_runs WHERE DATE(completed_at) = CURRENT_DATE AND status = 'success'", 1, "table"),
    ("Show pipeline failure rate by source",
     "SELECT pipeline_name, COUNT(*) FILTER(WHERE status='failed') * 100.0 / COUNT(*) as failure_rate FROM pipeline_runs GROUP BY pipeline_name", 4, "bar"),
    ("Which pipeline is slowest on average?",
     "SELECT pipeline_name, AVG(duration_seconds) as avg_duration FROM pipeline_runs WHERE status = 'success' GROUP BY pipeline_name ORDER BY avg_duration DESC", 4, "bar"),
    ("Show records loaded trend last 7 days",
     "SELECT DATE(completed_at) as date, SUM(records_loaded) as total FROM pipeline_runs WHERE completed_at > NOW() - INTERVAL '7 days' GROUP BY DATE(completed_at) ORDER BY date", 7, "line"),
    ("How many incidents were resolved automatically?",
     "SELECT approval_status, COUNT(*) FROM incidents GROUP BY approval_status", 3, "pie"),
    ("What is total cost saved from query optimization?",
     "SELECT metric_value as total_saved FROM system_metrics WHERE metric_name = 'total_cost_saved'", 1, "table"),
    ("Show top 5 longest pipeline runs",
     "SELECT pipeline_name, run_id, duration_seconds FROM pipeline_runs ORDER BY duration_seconds DESC LIMIT 5", 5, "table"),
]

for q, sql, rows, chart in sample_queries:
    created = now - timedelta(days=random.randint(1, 30), hours=random.randint(0, 12))
    cur.execute("""
        INSERT INTO query_history
          (id, question, generated_sql, optimized_sql, rows_returned,
           execution_time_ms, chart_type, feedback, created_at)
        VALUES (gen_random_uuid()::text, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (q, sql, sql, rows, random.randint(80, 800), chart,
          random.choice([1, 1, 1, -1]), created))

optimizations = [
    ("SELECT * FROM pipeline_runs WHERE status = 'success'",
     "SELECT id, pipeline_name, records_loaded, completed_at FROM pipeline_runs WHERE status = 'success' LIMIT 1000",
     ["Replaced SELECT * with explicit columns", "Added LIMIT 1000"], 34.2, 0.34),
    ("SELECT * FROM incidents",
     "SELECT id, pipeline_name, anomaly_type, confidence_score, approval_status, created_at FROM incidents LIMIT 1000",
     ["Replaced SELECT * with explicit columns", "Added LIMIT 1000"], 28.7, 0.29),
    ("SELECT * FROM pipeline_metrics WHERE recorded_at > '2024-01-01'",
     "SELECT pipeline_name, metric_name, metric_value, recorded_at FROM pipeline_metrics WHERE recorded_at > '2024-01-01' LIMIT 1000",
     ["Replaced SELECT * with explicit columns", "Added LIMIT 1000"], 41.3, 0.41),
]

total_saved = 0.0
for orig, opt, changes, savings_pct, dollar in optimizations:
    created = now - timedelta(days=random.randint(1, 20))
    cur.execute("""
        INSERT INTO query_optimizations
          (id, original_sql, optimized_sql, changes_made, savings_percent,
           dollar_savings, execution_time_before_ms, execution_time_after_ms, created_at)
        VALUES (gen_random_uuid()::text, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
    """, (orig, opt, str(changes).replace("'", '"'), savings_pct, dollar,
          random.randint(400, 800), random.randint(200, 500), created))
    total_saved += dollar

cur.execute("""
    INSERT INTO system_metrics (id, metric_name, metric_value, updated_at)
    VALUES (gen_random_uuid()::text, 'total_cost_saved', %s, NOW())
    ON CONFLICT (metric_name) DO UPDATE SET metric_value = EXCLUDED.metric_value, updated_at = NOW()
""", (round(total_saved, 2),))

conn.commit()
print(f"✅ Query history + cost savings seeded. Total saved: ${round(total_saved, 2)}")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — INSIGHTS
# ═══════════════════════════════════════════════════════════════════════════════
insights = [
    ("Pipeline Failure Spike Detected", "pipeline_rest_api_to_snowflake experienced 3 failures in the last 24 hours — 15x above its 7-day average of 0.2 failures/day.", "anomaly", "3 failures", "24h"),
    ("Record Volume Growing", "pipeline_csv_to_snowflake loaded 47,832 records yesterday — a 23% increase over the 7-day average, suggesting upstream data growth.", "opportunity", "+23% volume", "7d"),
    ("Cost Optimization Working", "3 query rewrites saved $1.04 this week — SELECT * queries reduced by 100% across all monitored sessions.", "info", "$1.04 saved", "7d"),
    ("Self-Healing Success Rate", "5 of 6 pipeline incidents were resolved autonomously in the last 30 days — 83% auto-heal rate with avg confidence of 0.93.", "opportunity", "83% auto-heal", "30d"),
    ("Google Sheets Reliability Risk", "pipeline_google_sheets_to_snowflake has the highest failure rate at 8.3% over 90 days — credential rotation policy needs review.", "warning", "8.3% failure rate", "90d"),
    ("RAG Cache Improving", "Learning Agent has stored 8 resolved fixes — Fix Writer Agent now retrieves cached fixes for 60% of similar anomalies, reducing Groq API calls.", "info", "60% cache hit", "30d"),
    ("Peak Ingestion Hours", "78% of all records are loaded between 02:00–06:00 UTC — consider staggering DAG schedules to avoid connection pool exhaustion.", "opportunity", "78% off-peak", "7d"),
    ("Slow Pipeline Alert", "pipeline_postgresql_to_snowflake average duration increased from 42s to 94s over the last 14 days — index on updated_at column recommended.", "warning", "+124% slower", "14d"),
    ("Zero-Failure Day", "All 4 pipelines completed successfully on June 10 — 1,847 total records loaded with 0 failures across 8 DAG runs.", "info", "0 failures", "24h"),
    ("dbt Models Health", "6 dbt models last ran successfully — 4 mart tables and 2 staging views. Next recommended run: add incremental materialization to reduce runtime.", "info", "6 models OK", "7d"),
]

for title, insight, severity, metric, window in insights:
    cur.execute("""
        INSERT INTO insights (id, title, insight, severity, metric, time_window, table_name, generated_at)
        VALUES (gen_random_uuid()::text, %s, %s, %s, %s, %s, 'pipeline_runs', NOW())
    """, (title, insight, severity, metric, window))

conn.commit()
print(f"✅ Insights seeded: {len(insights)}")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5 — TRAIN ISOLATION FOREST MODEL
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from backend.agents.healing.monitoring_agent import MonitoringAgent
    agent = MonitoringAgent()
    trained = agent.train_model()
    print(f"✅ Isolation Forest trained and saved: {trained}")
except Exception as e:
    print(f"⚠️  Isolation Forest training skipped: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6 — SEED CHROMADB (Learning Agent RAG)
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from backend.agents.learning.learning_agent import LearningAgent
    la = LearningAgent()

    rag_fixes = [
        ("rest_api", "zero_load", "REST API changed response format",
         "def apply_fix(df):\n    rename_map = {c: c.lower().replace(' ','_') for c in df.columns}\n    return df.rename(columns=rename_map).dropna(how='all')\ndef verify(b,a): return len(a)>=len(b)*0.9", 11, 0.917),
        ("postgresql", "row_count_drop", "PostgreSQL cursor field was reset to epoch",
         "def apply_fix(df):\n    import pandas as pd\n    from datetime import datetime,timedelta\n    if 'updated_at' in df.columns:\n        df['updated_at']=pd.to_datetime(df['updated_at'])\n        df=df[df['updated_at']>=datetime.utcnow()-timedelta(days=1)]\n    return df\ndef verify(b,a): return len(a)>0", 12, 1.0),
        ("csv", "ml_anomaly", "New column added to parquet schema causing type inference failure",
         "def apply_fix(df):\n    cols=['VendorID','trip_distance','fare_amount','total_amount']\n    existing=[c for c in cols if c in df.columns]\n    return df[existing].copy()\ndef verify(b,a): return len(a)>len(b)*0.5", 10, 0.833),
        ("google_sheets", "consecutive_failures", "Service account credentials expired after 30-day rotation policy",
         "def apply_fix(df):\n    df.columns=[c.strip().lower().replace(' ','_') for c in df.columns]\n    return df.dropna(how='all')\ndef verify(b,a): return not a.empty", 11, 0.917),
        ("postgresql", "zero_load", "Source DB max_connections limit hit by concurrent DAG tasks",
         "def apply_fix(df):\n    import pandas as pd\n    for col in df.select_dtypes(include=['object']).columns:\n        try: df[col]=pd.to_numeric(df[col])\n        except: pass\n    return df\ndef verify(b,a): return len(a)>0", 11, 0.917),
    ]

    for i, (pipeline, atype, cause, code, tests, conf) in enumerate(rag_fixes):
        la.store_fix({
            'incident_id': f'seed-incident-{i}',
            'pipeline_name': f'pipeline_{pipeline}_to_snowflake',
            'anomaly_type': atype,
            'root_cause': cause,
            'fix_code': code,
            'fix_language': 'python',
            'tests_passed': tests,
            'confidence_score': conf,
        })

    sample_qs = [
        ("How many records loaded today?", "SELECT COUNT(*) FROM pipeline_runs WHERE DATE(completed_at)=CURRENT_DATE", 1, "table"),
        ("Show failure rate by pipeline", "SELECT pipeline_name, COUNT(*) FILTER(WHERE status='failed')*100.0/COUNT(*) FROM pipeline_runs GROUP BY pipeline_name", 4, "bar"),
        ("Average pipeline duration", "SELECT pipeline_name, AVG(duration_seconds) FROM pipeline_runs GROUP BY pipeline_name", 4, "bar"),
    ]
    for q, sql, rows, chart in sample_qs:
        la.store_query(q, sql, {'rows_returned': rows, 'chart_type': chart, 'execution_time_ms': random.randint(80, 400)})

    stats = la.get_stats()
    print(f"✅ ChromaDB seeded: fixes={stats.get('total_fixes_stored')}, queries={stats.get('total_queries_stored')}")
except Exception as e:
    print(f"⚠️  ChromaDB seeding skipped: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7 — SEED DBT_RUNS
# ═══════════════════════════════════════════════════════════════════════════════
for i in range(5):
    run_date = now - timedelta(days=i * 7)
    cur.execute("""
        INSERT INTO dbt_runs
          (id, triggered_by, models_generated, models_succeeded, models_failed,
           tests_passed, tests_failed, mart_tables_created, run_output, created_at)
        VALUES (gen_random_uuid()::text, 'seed', 6, %s, %s, %s, %s, %s::jsonb, %s, %s)
    """, (random.randint(5, 6), random.randint(0, 1),
          random.randint(10, 12), random.randint(0, 2),
          '["fct_trips","dim_customers","fct_ecommerce_summary","dim_taxi_zones"]',
          f'Completed in {random.randint(12, 45)}s. 6 models processed.',
          run_date))

conn.commit()
print("✅ dbt_runs seeded")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 8 — VERIFY EVERYTHING
# ═══════════════════════════════════════════════════════════════════════════════
print("\n══════ SEED VERIFICATION ══════")
tables = ['pipelines', 'pipeline_runs', 'pipeline_metrics',
          'incidents', 'query_history', 'query_optimizations',
          'system_metrics', 'insights', 'dbt_runs']

for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    status = "✅" if count > 0 else "❌"
    print(f"  {status} {table}: {count} rows")

cur.execute("SELECT metric_value FROM system_metrics WHERE metric_name='total_cost_saved'")
row = cur.fetchone()
print(f"\n  \U0001f4b0 Total cost saved: ${row[0] if row else 0:.2f}")

try:
    from backend.agents.learning.learning_agent import LearningAgent
    stats = LearningAgent().get_stats()
    print(f"  \U0001f9e0 ChromaDB fixes: {stats.get('total_fixes_stored')}, queries: {stats.get('total_queries_stored')}")
except Exception as e:
    print(f"  ⚠️  ChromaDB stats unavailable: {e}")

print("\n✅ Seed complete — open http://localhost:3001 to see live data")
conn.close()
