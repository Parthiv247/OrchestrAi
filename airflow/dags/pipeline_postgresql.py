"""DAG: pipeline_postgresql_to_snowflake — every 6 hours."""
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

from backend.connectors.sources.postgresql_source import PostgreSQLSource, DEMO_CONFIG
from backend.connectors.destination.snowflake_loader import SnowflakeLoader
from airflow.dags.utils.lineage import save_pipeline_run_stats

DAG_ID = "pipeline_postgresql_to_snowflake"
TARGET_TABLE = "USERS_SYNC"
SOURCE = "postgresql"
RUN_ID = str(uuid.uuid4())

default_args = {
    "owner": "orchestrai",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "email": [os.environ.get("ALERT_EMAIL", "admin@orchestrai.com")],
}


def extract(**ctx):
    src = PostgreSQLSource(DEMO_CONFIG)
    tables = src.list_tables()
    table = tables[0] if tables else "users"
    df = src.extract(table)
    row_count = len(df)
    ctx["ti"].xcom_push(key="df_json", value=df.to_json(date_format="iso"))
    ctx["ti"].xcom_push(key="row_count", value=row_count)
    ctx["ti"].xcom_push(key="table", value=table)
    print("[extract] {} rows from {}".format(row_count, table))


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
    loader.create_table_from_dataframe(df, TARGET_TABLE, "RAW")
    loaded = loader.append(df, TARGET_TABLE, "RAW", source=SOURCE, run_id=RUN_ID)
    ti.xcom_push(key="rows_loaded", value=loaded)
    print("[load] {} rows loaded".format(loaded))


def quality_check(**ctx):
    ti = ctx["ti"]
    rows_loaded = ti.xcom_pull(key="rows_loaded", task_ids="load")
    row_count = ti.xcom_pull(key="row_count", task_ids="extract")
    if not rows_loaded or rows_loaded == 0:
        raise ValueError("Quality check failed: 0 rows loaded")
    df = pd.read_json(ti.xcom_pull(key="df_json", task_ids="transform"))
    for col in df.columns:
        null_pct = df[col].isna().mean()
        if null_pct > 0.10:
            print("[quality_check] WARNING: column {} has {:.1%} nulls".format(col, null_pct))
    save_pipeline_run_stats(
        pipeline_name="postgresql_to_snowflake", run_id=RUN_ID,
        records_ingested=row_count or 0, records_loaded=rows_loaded,
        records_failed=(row_count or 0) - rows_loaded, status="success",
        dag_id=DAG_ID,
    )
    print("[quality_check] PASSED — {} rows".format(rows_loaded))


with DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description="Ingest PostgreSQL tables → Snowflake/dest every 6h",
    schedule_interval="0 */6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["etl", "postgresql", "phase1"],
) as dag:
    t_extract = PythonOperator(task_id="extract", python_callable=extract)
    t_transform = PythonOperator(task_id="transform", python_callable=transform)
    t_load = PythonOperator(task_id="load", python_callable=load)
    t_qc = PythonOperator(task_id="quality_check", python_callable=quality_check)
    t_extract >> t_transform >> t_load >> t_qc
