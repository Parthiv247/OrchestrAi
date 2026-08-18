"""DAG: pipeline_google_sheets_to_snowflake — daily at 6am."""
import sys, os
sys.path.insert(0, "/Users/parthivpatel/OrchetraAI")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_USER", "admin")
os.environ.setdefault("POSTGRES_PASSWORD", "orchestrai_secret")
os.environ.setdefault("POSTGRES_DB", "orchestrai")

import uuid
from datetime import datetime, timedelta, timezone

import pandas as pd
from airflow import DAG
from airflow.operators.python import PythonOperator

from backend.connectors.sources.google_sheets_source import GoogleSheetsSource, DEMO_CONFIG
from backend.connectors.destination.snowflake_loader import SnowflakeLoader
from airflow.dags.utils.lineage import save_pipeline_run_stats

DAG_ID = "pipeline_google_sheets_to_snowflake"
TARGET_TABLE = "CLASS_DATA"
SOURCE = "google_sheets"
RUN_ID = str(uuid.uuid4())

default_args = {
    "owner": "orchestrai",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "email": [os.environ.get("ALERT_EMAIL", "admin@orchestrai.com")],
}


def extract(**ctx):
    src = GoogleSheetsSource(DEMO_CONFIG)
    df = src.extract()
    row_count = len(df)
    ctx["ti"].xcom_push(key="df_json", value=df.to_json(date_format="iso"))
    ctx["ti"].xcom_push(key="row_count", value=row_count)
    print("[extract] {} rows from Google Sheets".format(row_count))


def transform(**ctx):
    ti = ctx["ti"]
    df = pd.read_json(ti.xcom_pull(key="df_json", task_ids="extract"))
    df["_SOURCE"] = SOURCE
    df["_INGESTED_AT"] = datetime.now(timezone.utc).isoformat()
    df["_RUN_ID"] = RUN_ID
    row_count = len(df)
    ti.xcom_push(key="df_json", value=df.to_json(date_format="iso"))
    ti.xcom_push(key="row_count", value=row_count)
    print("[transform] {} rows".format(row_count))


def load(**ctx):
    ti = ctx["ti"]
    df = pd.read_json(ti.xcom_pull(key="df_json", task_ids="transform"))
    loader = SnowflakeLoader()
    loader.create_schema_if_not_exists("RAW")
    # Sheet schema is variable, so derive a deterministic surrogate key from the
    # business columns (stable across runs) and idempotently MERGE on it.
    business_cols = [c for c in df.columns if not c.startswith("_")]
    df = loader.add_surrogate_key(df, key_cols=business_cols, key_name="_PK")
    loaded = loader.upsert(df, TARGET_TABLE, primary_key="_PK", schema="RAW",
                           source=SOURCE, run_id=RUN_ID)
    ti.xcom_push(key="rows_loaded", value=loaded)
    print("[load] {} rows merged on _PK".format(loaded))


def quality_check(**ctx):
    ti = ctx["ti"]
    rows_loaded = ti.xcom_pull(key="rows_loaded", task_ids="load") or 0
    row_count = ti.xcom_pull(key="row_count", task_ids="extract") or 0
    if rows_loaded == 0:
        raise ValueError("Quality check failed: 0 rows loaded")
    save_pipeline_run_stats(
        pipeline_name="google_sheets_to_snowflake", run_id=RUN_ID,
        records_ingested=row_count, records_loaded=rows_loaded,
        records_failed=row_count - rows_loaded, status="success",
        dag_id=DAG_ID,
    )
    print("[quality_check] PASSED — {} rows".format(rows_loaded))


with DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description="Ingest Google Sheets (Class Data) → Snowflake/dest daily at 6am",
    schedule_interval="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["etl", "google_sheets", "phase1"],
) as dag:
    t_extract = PythonOperator(task_id="extract", python_callable=extract)
    t_transform = PythonOperator(task_id="transform", python_callable=transform)
    t_load = PythonOperator(task_id="load", python_callable=load)
    t_qc = PythonOperator(task_id="quality_check", python_callable=quality_check)
    t_extract >> t_transform >> t_load >> t_qc
