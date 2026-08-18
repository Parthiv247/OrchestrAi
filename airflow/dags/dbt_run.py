from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator

default_args = {
    "owner": "orchestrai",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

DBT_PROJECT_DIR = "/opt/airflow/dbt_project"

with DAG(
    dag_id="dbt_run",
    default_args=default_args,
    description="Run dbt models and tests after ingestion",
    schedule="0 4 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["dbt", "transformation"],
) as dag:

    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end")

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt deps",
    )

    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt run --select staging",
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt run --select marts",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt test",
    )

    dbt_generate_docs = BashOperator(
        task_id="dbt_generate_docs",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt docs generate",
    )

    start >> dbt_deps >> dbt_run_staging >> dbt_run_marts >> dbt_test >> dbt_generate_docs >> end
