from __future__ import annotations

import datetime as dt
from pathlib import Path

import pendulum
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import dag, get_current_context, task

POSTGRES_CONN_ID = "news_postgres"


@dag(
    dag_id="multimodal_news_etl",
    schedule="0 0 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    dagrun_timeout=dt.timedelta(minutes=60),
    tags=["news", "multimodal", "etl"],
)
def multimodal_news_etl():
    create_news_records = SQLExecuteQueryOperator(
        task_id="create_news_records",
        conn_id=POSTGRES_CONN_ID,
        sql="sql/create_news_records.sql",
    )

    create_news_records_temp = SQLExecuteQueryOperator(
        task_id="create_news_records_temp",
        conn_id=POSTGRES_CONN_ID,
        sql="sql/create_news_records_temp.sql",
    )

    merge_news_records = SQLExecuteQueryOperator(
        task_id="merge_news_records",
        conn_id=POSTGRES_CONN_ID,
        sql="sql/merge_records.sql",
    )

    @task
    def fetch_live_sources() -> list[str]:
        from news_ingestion.logging_config import configure_logging
        from news_ingestion.pipeline import fetch_live_sources as run_fetch_live_sources

        configure_logging()
        context = get_current_context()
        return [str(path) for path in run_fetch_live_sources(context["run_id"])]

    @task
    def transform_live_sources() -> str:
        from news_ingestion.logging_config import configure_logging
        from news_ingestion.pipeline import transform_live_run as run_transform_live_run

        configure_logging()
        context = get_current_context()
        return str(run_transform_live_run(context["run_id"]))

    @task
    def load_processed_records(processed_records_path: str) -> int:
        from news_ingestion.database import load_processed_records_to_temp
        from news_ingestion.logging_config import configure_logging

        configure_logging()
        postgres_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        conn = postgres_hook.get_conn()
        return load_processed_records_to_temp(Path(processed_records_path), conn)

    extract = fetch_live_sources()
    transform = transform_live_sources()
    load = load_processed_records(transform)  # ty: ignore[invalid-argument-type]

    [create_news_records, create_news_records_temp] >> extract >> transform
    load >> merge_news_records


multimodal_news_etl()
