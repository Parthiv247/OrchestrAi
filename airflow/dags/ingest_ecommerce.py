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
    dag_id="ingest_ecommerce",
    default_args=default_args,
    description="Ingest e-commerce orders/products data from Kafka into PostgreSQL",
    schedule="@hourly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ingestion", "ecommerce", "kafka"],
) as dag:

    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end")

    def consume_kafka_events(**context):
        """TODO: Consume events from Kafka topic ecommerce.orders using kafka-python."""
        print("Consuming messages from Kafka topic ecommerce.orders")

    def transform_and_load(**context):
        """TODO: Transform JSON events and upsert into raw.ecommerce_orders."""
        print("Transforming and loading ecommerce events")

    def update_anomaly_baseline(**context):
        """TODO: Update IsolationForest baseline with new volume/latency metrics."""
        print("Updating anomaly detection baseline")

    consume = PythonOperator(task_id="consume_kafka_events", python_callable=consume_kafka_events)
    transform = PythonOperator(task_id="transform_and_load", python_callable=transform_and_load)
    anomaly = PythonOperator(task_id="update_anomaly_baseline", python_callable=update_anomaly_baseline)

    start >> consume >> transform >> anomaly >> end
