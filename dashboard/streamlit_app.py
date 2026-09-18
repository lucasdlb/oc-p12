from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import streamlit as st

from news_ingestion.config import PROJECT_ROOT
from news_ingestion.metrics import (
    latest_metrics_path,
    load_metrics,
    processed_record_metrics,
)

DEFAULT_PROCESSED_PATH = PROJECT_ROOT / "data" / "processed" / "processed_records.json"
DEFAULT_DATABASE_URL = "postgresql://news:news@localhost:5433/news"


class DatabaseMetricsError(RuntimeError):
    pass


def main() -> None:
    st.set_page_config(
        page_title="Multimodal ETL Dashboard",
        page_icon=":bar_chart:",
        layout="wide",
    )
    st.title("Multimodal News ETL Dashboard")
    st.caption(
        "Pipeline metrics, processed-data quality, and optional PostgreSQL load checks."
    )

    processed_path, metrics_path, database_url = render_sidebar()
    records = load_records(processed_path)
    data_metrics = processed_record_metrics(records) if records else {}
    run_metrics = (
        load_metrics(metrics_path) if metrics_path and metrics_path.exists() else {}
    )

    render_top_metrics(data_metrics, run_metrics)

    tabs = st.tabs(["Pipeline", "Processed Data", "Database", "Samples"])
    with tabs[0]:
        render_pipeline_tab(run_metrics)
    with tabs[1]:
        render_processed_data_tab(data_metrics, records)
    with tabs[2]:
        render_database_tab(database_url)
    with tabs[3]:
        render_samples_tab(records)


def render_sidebar() -> tuple[Path, Path | None, str]:
    st.sidebar.header("Inputs")
    processed_path = Path(
        st.sidebar.text_input("Processed records", str(DEFAULT_PROCESSED_PATH))
    )
    detected_metrics_path = latest_metrics_path()
    metrics_value = str(detected_metrics_path) if detected_metrics_path else ""
    metrics_input = st.sidebar.text_input("Run metrics", metrics_value)
    database_url = st.sidebar.text_input(
        "Database URL",
        os.getenv("NEWS_DASHBOARD_DATABASE_URL", DEFAULT_DATABASE_URL),
        type="password",
    )
    st.sidebar.caption(
        "Leave database unavailable if you only need file-based dashboard metrics."
    )
    return processed_path, Path(metrics_input) if metrics_input else None, database_url


@st.cache_data(show_spinner=False)
def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        msg = f"Expected {path} to contain a JSON array."
        raise TypeError(msg)
    return [record for record in records if isinstance(record, dict)]


def render_top_metrics(
    data_metrics: dict[str, Any], run_metrics: dict[str, Any]
) -> None:
    extraction = as_dict(run_metrics.get("extraction"))
    load = as_dict(run_metrics.get("load"))
    columns = st.columns(6)
    columns[0].metric("Processed records", data_metrics.get("total_records", 0))
    columns[1].metric("Valid records", f"{data_metrics.get('valid_record_rate', 0)}%")
    columns[2].metric("Multimodal", f"{data_metrics.get('multimodal_rate', 0)}%")
    columns[3].metric(
        "Valid article images",
        f"{data_metrics.get('valid_article_image_rate', 0)}%",
    )
    columns[4].metric("Sources failed", extraction.get("sources_failed", "n/a"))
    columns[5].metric("Loaded records", load.get("loaded_records", "n/a"))


def render_pipeline_tab(run_metrics: dict[str, Any]) -> None:
    if not run_metrics:
        st.info("No structured metrics file found yet.")
        return

    st.subheader("Run Summary")
    st.json(
        {
            "run_id": run_metrics.get("run_id", "static/manual"),
            "updated_at": run_metrics.get("updated_at"),
        },
        expanded=False,
    )

    extraction = as_dict(run_metrics.get("extraction"))
    transformation = as_dict(run_metrics.get("transformation"))
    load = as_dict(run_metrics.get("load"))
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### Extraction")
        st.json(extraction or {"status": "not available"}, expanded=False)
    with col2:
        st.markdown("### Transformation")
        st.json(transformation or {"status": "not available"}, expanded=False)
    with col3:
        st.markdown("### Load")
        st.json(load or {"status": "not available"}, expanded=False)

    sources = extraction.get("sources")
    if isinstance(sources, list) and sources:
        st.subheader("Source-Level Extraction")
        st.dataframe(sources, use_container_width=True)


def render_processed_data_tab(
    data_metrics: dict[str, Any], records: list[dict[str, Any]]
) -> None:
    if not records:
        st.warning("No processed records found at the configured path.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Records By Source")
        render_count_chart(as_counter(data_metrics.get("records_by_source")))
    with col2:
        st.subheader("Validation Errors")
        validation_errors = as_counter(data_metrics.get("validation_errors"))
        if validation_errors:
            render_count_chart(validation_errors)
        else:
            st.success("No validation errors found.")

    st.subheader("Data Quality Metrics")
    st.dataframe(flatten_metrics(data_metrics), use_container_width=True)


def render_database_tab(database_url: str) -> None:
    st.subheader("PostgreSQL Load Check")
    if not database_url:
        st.info("No database URL configured.")
        return

    if st.button("Query database"):
        try:
            db_metrics = query_database_metrics(database_url)
        except DatabaseMetricsError as exc:
            st.error(f"Database metrics unavailable: {exc}")
            return
        st.success("Database query completed.")
        st.dataframe(flatten_metrics(db_metrics), use_container_width=True)
        if "records_by_source" in db_metrics:
            st.subheader("Loaded Records By Source")
            render_count_chart(as_counter(db_metrics["records_by_source"]))


def render_samples_tab(records: list[dict[str, Any]]) -> None:
    if not records:
        st.info("No records to display.")
        return
    source_filter = st.selectbox(
        "Filter by source",
        ["all", *sorted({str(record.get("extracted_from")) for record in records})],
    )
    filtered = records
    if source_filter != "all":
        filtered = [
            record
            for record in records
            if str(record.get("extracted_from")) == source_filter
        ]
    preview = [sample_record(record) for record in filtered[:100]]
    st.dataframe(preview, use_container_width=True)


def query_database_metrics(database_url: str) -> dict[str, Any]:
    try:
        import psycopg
    except ImportError as exc:
        msg = "Install psycopg[binary] or rebuild the dashboard image to query PostgreSQL."
        raise DatabaseMetricsError(msg) from exc

    try:
        with psycopg.connect(database_url) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM news_records")
            total_records = fetch_count(cursor)
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM news_records
                WHERE is_multimodal = true
                """
            )
            multimodal_records = fetch_count(cursor)
            cursor.execute(
                """
                SELECT extracted_from, COUNT(*)
                FROM news_records
                GROUP BY extracted_from
                ORDER BY COUNT(*) DESC
                """
            )
            records_by_source = dict(cursor.fetchall())
    except psycopg.Error as exc:
        raise DatabaseMetricsError(str(exc)) from exc

    return {
        "total_loaded_records": total_records,
        "loaded_multimodal_records": multimodal_records,
        "loaded_multimodal_rate": percentage(multimodal_records, total_records),
        "records_by_source": records_by_source,
    }


def fetch_count(cursor: Any) -> int:
    row = cursor.fetchone()
    if row is None:
        raise DatabaseMetricsError("Database count query returned no rows.")
    return int(row[0])


def render_count_chart(counts: Counter[str]) -> None:
    if not counts:
        st.info("No counts available.")
        return
    rows = [{"label": label, "count": count} for label, count in counts.most_common()]
    st.bar_chart(rows, x="label", y="count")
    st.dataframe(rows, use_container_width=True)


def flatten_metrics(metrics: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, value in metrics.items():
        if isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False)
        rows.append({"metric": key, "value": str(value)})
    return rows


def sample_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": record.get("record_type"),
        "extracted_from": record.get("extracted_from"),
        "source_name": record.get("source_name"),
        "is_multimodal": record.get("is_multimodal"),
        "validation_errors": ", ".join(record.get("validation_errors") or []),
        "text": shorten(record.get("text")),
    }


def shorten(value: object, max_length: int = 180) -> str:
    text = str(value or "")
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_counter(value: object) -> Counter[str]:
    if not isinstance(value, dict):
        return Counter()
    return Counter({str(key): int(count) for key, count in value.items()})


def percentage(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


if __name__ == "__main__":
    main()
