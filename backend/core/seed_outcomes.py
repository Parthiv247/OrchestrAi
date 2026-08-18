"""
seed_outcomes.py — Insert 45 synthetic healing_outcomes records spanning 30 days.

Demonstrates a clear learning curve:
  Week 1 (days 22-28 ago): avg MTTR ~280 s
  Week 2 (days 15-21 ago): avg MTTR ~195 s
  Week 3 (days  8-14 ago): avg MTTR ~130 s
  Week 4 (days  1-7  ago): avg MTTR  ~87 s

Run standalone:
    cd /path/to/backend && python3 core/seed_outcomes.py
"""
import os
import random
import uuid
from datetime import datetime, timedelta

import psycopg2

DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST", "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", 5432)),
    "dbname":   os.getenv("POSTGRES_DB", "orchestrai"),
    "user":     os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
}

# 5 anomaly types with realistic strategy names and initial success rates
ANOMALY_STRATEGIES = {
    "ZERO_LOAD": [
        ("restart_pipeline",       0.90),
        ("increase_timeout",       0.60),
    ],
    "SCHEMA_DRIFT": [
        ("schema_evolution_patch", 0.80),
        ("column_type_cast",       0.55),
    ],
    "THROUGHPUT_DROP": [
        ("scale_workers",          0.75),
        ("enable_batching",        0.65),
    ],
    "DATA_QUALITY_FAIL": [
        ("apply_dq_rules",         0.70),
        ("quarantine_bad_rows",    0.80),
    ],
    "CONNECTOR_TIMEOUT": [
        ("retry_with_backoff",     0.85),
        ("switch_replica",         0.50),
    ],
}

# Weekly MTTR targets (centre values in seconds); jitter applied per record
WEEKLY_MTTR = {
    1: 280.0,   # oldest week (worst)
    2: 195.0,
    3: 130.0,
    4:  87.0,   # most recent week (best)
}

PIPELINE_NAMES = [
    "sales_etl_prod",
    "user_events_pipeline",
    "inventory_sync",
    "finance_reporting",
    "clickstream_ingestion",
]


def _week_for_day_offset(days_ago: int) -> int:
    """Map days_ago (1-28) to week number 4→1 (most-recent → oldest)."""
    if days_ago <= 7:
        return 4
    elif days_ago <= 14:
        return 3
    elif days_ago <= 21:
        return 2
    else:
        return 1


def seed(clear_existing: bool = False):
    conn = psycopg2.connect(**DB_CONFIG, connect_timeout=10)
    cur = conn.cursor()

    if clear_existing:
        cur.execute("DELETE FROM healing_outcomes WHERE approved_by = 'seed_script'")
        conn.commit()
        print("Cleared existing seed data.")

    now = datetime.utcnow()
    records_inserted = 0

    # Distribute 45 records across 30 days — denser in recent weeks to mimic growth
    # Day distribution: 3 records in week 1, 8 in week 2, 14 in week 3, 20 in week 4
    day_pool: list[int] = (
        random.choices(range(22, 29), k=3) +   # week 1: ~3 records
        random.choices(range(15, 22), k=8) +   # week 2: ~8 records
        random.choices(range( 8, 15), k=14) +  # week 3: ~14 records
        random.choices(range( 1,  8), k=20)    # week 4: ~20 records
    )
    # Pad or trim to exactly 45
    while len(day_pool) < 45:
        day_pool.append(random.randint(1, 7))
    day_pool = day_pool[:45]

    anomaly_types = list(ANOMALY_STRATEGIES.keys())

    for i, days_ago in enumerate(day_pool):
        week = _week_for_day_offset(days_ago)
        target_mttr = WEEKLY_MTTR[week]
        jitter = random.uniform(-target_mttr * 0.25, target_mttr * 0.25)
        mttr = max(10.0, target_mttr + jitter)

        anomaly_type = anomaly_types[i % len(anomaly_types)]
        strategies = ANOMALY_STRATEGIES[anomaly_type]
        strategy_name, base_success_rate = random.choice(strategies)
        # Success rate improves slightly in later weeks
        adj_rate = min(0.98, base_success_rate + (week - 1) * 0.04)
        outcome = "approved" if random.random() < adj_rate else "rejected"

        incident_id = str(uuid.uuid4())
        pipeline_name = random.choice(PIPELINE_NAMES)
        resolved_at = now - timedelta(days=days_ago, hours=random.uniform(0, 23))
        detection_at = resolved_at - timedelta(seconds=mttr)
        confidence = round(random.uniform(0.55, 0.97), 3)

        cur.execute(
            """
            INSERT INTO healing_outcomes
                (incident_id, pipeline_name, anomaly_type, healing_strategy,
                 fix_code_hash, outcome, mttr_seconds, confidence_score,
                 approved_by, detection_at, resolved_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                incident_id,
                pipeline_name,
                anomaly_type,
                strategy_name,
                uuid.uuid4().hex[:16],   # synthetic hash
                outcome,
                round(mttr, 2),
                confidence,
                "seed_script",
                detection_at,
                resolved_at,
                resolved_at,
            ),
        )
        records_inserted += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n=== Seed complete: {records_inserted} records inserted ===\n")
    print("Weekly MTTR targets:")
    for w in sorted(WEEKLY_MTTR):
        print(f"  Week {w} (days {(4-w)*7+1}–{(4-w+1)*7} ago): {WEEKLY_MTTR[w]:.0f}s target avg MTTR")

    print("\nLearning curve summary:")
    print("  W1 ~280s → W2 ~195s → W3 ~130s → W4 ~87s  (69% MTTR reduction)")
    print("\nRun the backend and hit GET /api/learning/mttr-trend to confirm.\n")


if __name__ == "__main__":
    import sys
    clear = "--clear" in sys.argv
    seed(clear_existing=clear)
