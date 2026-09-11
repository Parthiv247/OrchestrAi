"""
Lightweight per-pipeline ingestion scheduler.

A background thread wakes every 60s, and for each active pipeline with an interval
schedule, triggers its ETL job when enough time has elapsed since the last run.
Intervals are derived from the pipeline's `schedule` value (cron presets emitted by
the builder UI). No external scheduler/cron daemon required.
"""
import logging
import re
import threading
import uuid
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

logger = logging.getLogger("orchestrai.scheduler")

# Cron presets emitted by the UI → interval in minutes.
_CRON_MINUTES = {
    "*/30 * * * *": 30,
    "0 * * * *": 60,
    "0 */3 * * *": 180,
    "0 */6 * * *": 360,
    "0 */12 * * *": 720,
    "0 0 * * *": 1440,
    "@hourly": 60,
    "@daily": 1440,
}

_stop = threading.Event()
_thread = None


def interval_minutes(schedule):
    """Map a schedule string to an interval in minutes (None = manual/no schedule)."""
    if not schedule:
        return None
    s = str(schedule).strip()
    if s in _CRON_MINUTES:
        return _CRON_MINUTES[s]
    m = re.match(r"^\*/(\d+) \* \* \* \*$", s)        # every N minutes
    if m:
        return int(m.group(1))
    m = re.match(r"^0 \*/(\d+) \* \* \*$", s)          # every N hours
    if m:
        return int(m.group(1)) * 60
    return None


def _tick():
    # Imported lazily to avoid a circular import at module load.
    from .api.routes.pipelines import DB_CONFIG_ETL, _ensure_etl_tables, _run_etl_job

    conn = psycopg2.connect(**DB_CONFIG_ETL, connect_timeout=10)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, name, schedule, source_config FROM pipelines WHERE status = 'active'")
    pipelines = cur.fetchall()

    now = datetime.now(timezone.utc)
    triggered = 0
    for p in pipelines:
        mins = interval_minutes(p.get("schedule"))
        if not mins:
            continue
        cur.execute(
            "SELECT MAX(completed_at) AS last FROM pipeline_runs WHERE pipeline_name = %s OR dag_id = %s",
            (p["name"], p["id"]),
        )
        _row = cur.fetchone()
        last = _row["last"] if _row else None
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        due = last is None or (now - last).total_seconds() >= mins * 60
        if not due:
            continue

        # sync_mode from source_config when present
        sync_mode = "full_refresh"
        sc = p.get("source_config")
        if isinstance(sc, dict):
            sync_mode = sc.get("sync_mode", sync_mode)

        job_id = str(uuid.uuid4())
        try:
            _ensure_etl_tables(conn)
            cur.execute(
                "INSERT INTO etl_job_queue (id, pipeline_id, sync_mode, status, scheduled_at) "
                "VALUES (%s, %s, %s, 'queued', NOW())",
                (job_id, p["id"], sync_mode),
            )
        except Exception as e:
            logger.warning("scheduler enqueue failed for %s: %s", p["name"], e)
            continue

        logger.info("scheduler: triggering %s (every %dm)", p["name"], mins)
        threading.Thread(
            target=_run_etl_job, args=(job_id, p["id"], sync_mode, ""), daemon=True
        ).start()
        triggered += 1

    conn.close()
    return triggered


def _loop():
    # small initial delay so the app finishes booting
    _stop.wait(15)
    while not _stop.is_set():
        try:
            triggered = _tick()
            if triggered:
                logger.info("[scheduler] triggered %d pipeline run(s)", triggered)
        except Exception as e:
            import traceback
            logger.error("[scheduler] tick ERROR: %s\n%s", e, traceback.format_exc())
        _stop.wait(60)  # re-check every minute


def start():
    import os
    if os.getenv("SCHEDULER_DISABLED", "").lower() in ("1", "true", "yes"):
        logger.info("Pipeline ingestion scheduler DISABLED (SCHEDULER_DISABLED=true)")
        return
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="pipeline-scheduler")
    _thread.start()
    logger.info("Pipeline ingestion scheduler started")


def stop():
    _stop.set()
