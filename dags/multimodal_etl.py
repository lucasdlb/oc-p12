"""Airflow DAG for the multimodal news ETL pipeline."""

from __future__ import annotations

import datetime as dt
from importlib.resources import files
from pathlib import Path

import pendulum
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import dag, get_current_context, task

POSTGRES_CONN_ID = "news_postgres"


def migration_sql(file_name: str) -> str:
    """Load a packaged SQL migration for an Airflow SQL task."""
    return (
        files("news_ingestion.sql.migrations")
        .joinpath(file_name)
        .read_text(encoding="utf-8")
    )


@dag(
    dag_id="multimodal_news_etl",
    schedule="0 */3 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=dt.timedelta(minutes=60),
    tags=["news", "multimodal", "etl"],
)
def multimodal_news_etl():
    """Define the multimodal news extraction, transform, and load DAG."""
    create_news_records = SQLExecuteQueryOperator(
        task_id="create_news_records",
        conn_id=POSTGRES_CONN_ID,
        sql=migration_sql("create_news_records.sql"),
    )

    create_news_records_staging = SQLExecuteQueryOperator(
        task_id="create_news_records_staging",
        conn_id=POSTGRES_CONN_ID,
        sql=migration_sql("create_news_records_staging.sql"),
        split_statements=True,
    )

    merge_news_records = SQLExecuteQueryOperator(
        task_id="merge_news_records",
        conn_id=POSTGRES_CONN_ID,
        sql=migration_sql("merge_records.sql"),
        parameters={"run_id": "{{ run_id }}"},
        split_statements=True,
    )

    @task
    def extract_live_sources() -> dict[str, object]:
        """Extract configured live sources for the current Airflow run."""
        from news_ingestion.composition import extract_live_sources as run_extraction
        from news_ingestion.logging_config import configure_logging

        configure_logging()
        context = get_current_context()
        return run_extraction(context["run_id"]).to_serializable_dict()

    @task
    def transform_live_sources(extraction: dict[str, object]) -> str:
        """Transform live raw outputs for the current Airflow run."""
        from news_ingestion.composition import (
            transform_live_run as run_transform_live_run,
        )
        from news_ingestion.logging_config import configure_logging

        configure_logging()
        artifact_paths = extraction.get("artifact_paths")
        if not isinstance(artifact_paths, list) or not all(
            isinstance(path, str) for path in artifact_paths
        ):
            msg = "Extraction result contains invalid artifact paths."
            raise TypeError(msg)
        context = get_current_context()
        result = run_transform_live_run(
            [Path(path) for path in artifact_paths], context["run_id"]
        )
        return str(result.artifact_path)

    @task
    def load_processed_records_to_staging(processed_records_path: str) -> int:
        """Load processed records into the staging database table."""
        from news_ingestion.logging_config import configure_logging
        from news_ingestion.services.loading import load_processed_records_to_staging

        configure_logging()
        postgres_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        conn = postgres_hook.get_conn()
        context = get_current_context()
        return load_processed_records_to_staging(
            Path(processed_records_path), conn, run_id=context["run_id"]
        )

    extract = extract_live_sources()
    transform = transform_live_sources(extract)  # ty: ignore[invalid-argument-type]
    load = load_processed_records_to_staging(transform)  # ty: ignore[invalid-argument-type]

    create_news_records >> create_news_records_staging >> extract >> transform
    load >> merge_news_records


multimodal_news_etl()
