"""pipeline_runs stats saver for OrchestrAI Airflow DAGs."""
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)


def save_pipeline_run_stats(
    pipeline_name: str,
    run_id: str,
    records_ingested: int,
    records_loaded: int,
    records_failed: int,
    status: str,
    error_message: Optional[str] = None,
    dag_id: Optional[str] = None,
    duration_seconds: Optional[int] = None,
):
    """Insert a row into pipeline_runs table in PostgreSQL."""
    import psycopg2
    now = datetime.now(timezone.utc)
    try:
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", 5432)),
            dbname=os.environ.get("POSTGRES_DB", "orchestrai"),
            user=os.environ.get("POSTGRES_USER", "admin"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline_runs
                    (id, pipeline_name, dag_id, run_id, records_ingested,
                     records_transformed, records_loaded, records_failed,
                     status, error_message, started_at, completed_at, duration_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    str(uuid.uuid4()), pipeline_name, dag_id, run_id,
                    records_ingested, records_ingested, records_loaded, records_failed,
                    status, error_message, now, now, duration_seconds,
                ),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("[lineage] save_pipeline_run_stats failed: %s", e)
