from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator

default_args = {
    "owner": "orchestrai",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="ingest_nyc_taxi",
    default_args=default_args,
    description="Ingest NYC Taxi trip data into PostgreSQL staging",
    schedule="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ingestion", "nyc_taxi"],
) as dag:

    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end")

    def download_data(**context):
        """TODO: Download NYC Taxi parquet from public S3 and save to /tmp."""
        # Source: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
        print(f"Downloading NYC Taxi data for {context['ds']}")

    def validate_data(**context):
        """TODO: Run Great Expectations validation suite on raw file."""
        print("Validating schema, null rates, and row counts")

    def load_to_postgres(**context):
        """TODO: Load validated parquet into raw.nyc_taxi_trips using pandas + psycopg2."""
        print("Loading data to PostgreSQL raw schema")

    download = PythonOperator(task_id="download_data", python_callable=download_data)
    validate = PythonOperator(task_id="validate_data", python_callable=validate_data)
    load = PythonOperator(task_id="load_to_postgres", python_callable=load_to_postgres)

    start >> download >> validate >> load >> end
