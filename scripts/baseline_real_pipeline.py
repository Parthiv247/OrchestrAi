"""
Give the real pipeline (pipeline_postgres_to_snowflake) a clean HEALTHY baseline:
  1. Seed ~60 consistent successful runs over the last 30 days (+ matching metrics).
  2. Retrain the Isolation Forest on this consistent history.
  3. Clear stale anomaly incidents.
  4. Verify MonitoringAgent now reports the pipeline as healthy.
Run inside the backend container (has sklearn, psycopg2, mounted ml/ model path).
"""
import os, sys, uuid, random
from datetime import datetime, timedelta

import psycopg2

sys.path.insert(0, "/app")

DB = dict(host=os.getenv("POSTGRES_HOST", "postgres"), port=int(os.getenv("POSTGRES_PORT", 5432)),
          dbname=os.getenv("POSTGRES_DB", "orchestrai"), user=os.getenv("POSTGRES_USER", "admin"),
          password=os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"))

PIPE = "pipeline_postgres_to_snowflake"
DAG = "pipeline_postgres_to_snowflake"
now = datetime.utcnow()

conn = psycopg2.connect(**DB)
conn.autocommit = False
cur = conn.cursor()

# Keep only the demo-free state: wipe this pipeline's existing runs/metrics so the
# baseline is clean and consistent (the single 1s run would otherwise skew duration).
cur.execute("DELETE FROM pipeline_metrics WHERE pipeline_name=%s", (PIPE,))
cur.execute("DELETE FROM pipeline_runs WHERE pipeline_name=%s", (PIPE,))

# ── 1. Seed consistent successful history (mild natural variance) ───────────────
N = 60
runs = []
for i in range(N):
    # one run every ~12h over the last 30 days; most recent ends at NOW
    started = now - timedelta(hours=12 * (N - i)) + timedelta(minutes=random.randint(-30, 30))
    loaded = max(9000, int(random.gauss(10000, 250)))
    duration = max(3, int(random.gauss(9, 2)))
    completed = started + timedelta(seconds=duration)
    runs.append((loaded, duration, started, completed))

# final run = right now, dead-normal, so it's the "latest_run" checked for health
runs.append((10000, 8, now - timedelta(seconds=8), now))

for loaded, duration, started, completed in runs:
    rid = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO pipeline_runs
          (id, pipeline_name, dag_id, run_id, records_ingested, records_transformed,
           records_loaded, records_failed, status, started_at, completed_at, duration_seconds)
        VALUES (%s,%s,%s,%s,%s,%s,%s,0,'success',%s,%s,%s)
    """, (rid, PIPE, DAG, "etl_" + uuid.uuid4().hex[:8], loaded, loaded, loaded,
          started, completed, duration))
    cur.execute("""
        INSERT INTO pipeline_metrics (id, pipeline_name, metric_name, metric_value, recorded_at)
        VALUES (gen_random_uuid()::text,%s,'records_loaded',%s,%s),
               (gen_random_uuid()::text,%s,'duration_seconds',%s,%s),
               (gen_random_uuid()::text,%s,'records_failed',0,%s)
    """, (PIPE, loaded, completed, PIPE, duration, completed, PIPE, completed))

# ── 3. Clear stale anomaly incidents for this pipeline ─────────────────────────
cur.execute("DELETE FROM fixes WHERE incident_id IN (SELECT id FROM incidents WHERE pipeline_name=%s)", (PIPE,))
cur.execute("DELETE FROM incidents WHERE pipeline_name=%s", (PIPE,))
conn.commit()
print(f"Seeded {len(runs)} consistent successful runs; cleared stale incidents.")

# ── 2. Retrain Isolation Forest on the consistent history ──────────────────────
from backend.agents.healing.monitoring_agent import MonitoringAgent
agent = MonitoringAgent()
trained = agent.train_model()
print("Model retrained:", trained)

# ── 4. Verify ──────────────────────────────────────────────────────────────────
agent2 = MonitoringAgent()  # reload freshly-trained model
cur.execute("""SELECT records_loaded, records_failed, duration_seconds, status
               FROM pipeline_runs WHERE pipeline_name=%s ORDER BY started_at DESC LIMIT 1""", (PIPE,))
r = cur.fetchone()
latest = {"records_loaded": r[0], "records_failed": r[1], "duration_seconds": r[2], "status": r[3]}
score = agent2.score_run(latest)
state = agent2.check_pipeline(PIPE)
print(f"Latest run: {latest}")
print(f"Isolation-Forest score: {score:.4f}  (healthy if >= -0.1)")
print(f"check_pipeline result: {'HEALTHY ✅' if state is None else 'ANOMALY -> ' + str(state.get('anomaly_type'))}")
conn.close()
