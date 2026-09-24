"""Interactive Streamlit dashboard for ETL metrics and database records."""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import streamlit as st

from news_ingestion.config import get_settings
from news_ingestion.paths import project_paths
from news_ingestion.persistence.metrics import (
    calculate_percentage,
    load_metrics_or_empty,
)


class DatabaseMetricsError(RuntimeError):
    """Raised when database metrics cannot be queried."""


def main() -> None:
    """Render the Streamlit dashboard application."""
    st.set_page_config(
        page_title="Multimodal ETL Dashboard",
        page_icon=":bar_chart:",
        layout="wide",
    )
    st.title("Multimodal News ETL Dashboard")
    st.caption("Current PostgreSQL data quality and pipeline execution metrics by run.")

    settings = get_settings()
    paths = project_paths(settings)
    database_url = render_sidebar(settings.dashboard_database_url)
    pipeline_runs = load_pipeline_runs(paths.metrics_root)

    database_metrics: dict[str, Any] = {}
    database_error: str | None = None
    if database_url:
        try:
            database_metrics = query_database_metrics(database_url)
        except DatabaseMetricsError as exc:
            database_error = str(exc)
    else:
        database_error = "No database URL configured."

    render_top_metrics(database_metrics)

    database_tab, pipeline_tab, samples_tab = st.tabs(
        ["Database Overview", "Pipeline Runs", "Samples"]
    )
    with database_tab:
        render_database_overview(database_metrics, database_error)
    with pipeline_tab:
        render_pipeline_tab(pipeline_runs)
    with samples_tab:
        render_samples_tab(database_url, database_metrics, database_error)


def render_sidebar(configured_database_url: str) -> str:
    """Render connection settings and return the database URL."""
    st.sidebar.header("Inputs")
    database_url = st.sidebar.text_input(
        "Database URL",
        os.getenv("NEWS_DASHBOARD_DATABASE_URL", configured_database_url),
        type="password",
    )
    st.sidebar.caption(
        "Dataset metrics use PostgreSQL. Pipeline metrics use run files under "
        "data/metrics/runs."
    )
    return database_url


def render_top_metrics(database_metrics: dict[str, Any]) -> None:
    """Render database-wide KPI metrics."""
    columns = st.columns(6)
    columns[0].metric("Database records", database_metrics.get("total_records", "n/a"))
    columns[1].metric(
        "Valid records", format_percentage(database_metrics.get("valid_record_rate"))
    )
    columns[2].metric(
        "Multimodal", format_percentage(database_metrics.get("multimodal_rate"))
    )
    columns[3].metric(
        "Valid article images",
        format_percentage(database_metrics.get("valid_article_image_rate")),
    )
    columns[4].metric(
        "Sources", len(as_dict(database_metrics.get("records_by_source"))) or "n/a"
    )
    columns[5].metric("Latest load", database_metrics.get("latest_loaded_at") or "n/a")


def render_database_overview(
    database_metrics: dict[str, Any], database_error: str | None
) -> None:
    """Render aggregate metrics for the current database contents."""
    st.subheader("Current Database State")
    st.caption(
        "These metrics cover all unique records currently stored in news_records."
    )
    if database_error:
        st.error(f"Database metrics unavailable: {database_error}")
        return

    render_quality_warnings(database_metrics)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### Records By Source")
        render_count_chart(as_counter(database_metrics.get("records_by_source")))
    with col2:
        st.markdown("### Records By Type")
        render_count_chart(as_counter(database_metrics.get("records_by_type")))
    with col3:
        st.markdown("### Validation Errors")
        validation_errors = as_counter(database_metrics.get("validation_errors"))
        if validation_errors:
            render_count_chart(validation_errors)
        else:
            st.success("No validation errors found.")

    st.subheader("Data Quality Metrics")
    summary = {
        key: value
        for key, value in database_metrics.items()
        if key not in {"records_by_source", "records_by_type", "validation_errors"}
    }
    st.dataframe(flatten_metrics(summary), width="stretch")


def render_quality_warnings(database_metrics: dict[str, Any]) -> None:
    """Display monitoring-plan thresholds for the current database state."""
    total_records = database_metrics.get("total_records")
    valid_rate = database_metrics.get("valid_record_rate")
    image_rate = database_metrics.get("valid_article_image_rate")

    if total_records == 0:
        st.error("High priority: no records are loaded in news_records.")
    if isinstance(valid_rate, int | float) and valid_rate < 80:
        st.warning(f"Medium priority: valid-record rate is {valid_rate}%, below 80%.")
    if isinstance(image_rate, int | float) and image_rate < 50:
        st.warning(
            f"Medium priority: valid article-image rate is {image_rate}%, below 50%."
        )


def load_pipeline_runs(metrics_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Load valid run-scoped metrics files, newest first."""
    runs: list[tuple[Path, dict[str, Any]]] = []
    for path in metrics_root.glob("runs/*/metrics.json"):
        try:
            metrics = load_metrics_or_empty(path)
        except (OSError, TypeError, json.JSONDecodeError):
            continue
        if metrics:
            runs.append((path, metrics))
    return sorted(runs, key=lambda run: run[0].stat().st_mtime, reverse=True)


def render_pipeline_tab(pipeline_runs: list[tuple[Path, dict[str, Any]]]) -> None:
    """Render selectable run details and aggregate pipeline metrics."""
    if not pipeline_runs:
        st.info("No run-scoped pipeline metrics found.")
        return

    selected_index = st.selectbox(
        "Pipeline run",
        range(len(pipeline_runs)),
        format_func=lambda index: pipeline_run_label(pipeline_runs[index]),
    )
    selected_metrics = pipeline_runs[selected_index][1]
    selected_tab, aggregate_tab = st.tabs(["Selected Run", "All Runs"])
    with selected_tab:
        render_selected_pipeline_run(selected_metrics)
    with aggregate_tab:
        render_aggregate_pipeline_runs([metrics for _, metrics in pipeline_runs])


def pipeline_run_label(run: tuple[Path, dict[str, Any]]) -> str:
    """Return a concise label for a pipeline run selector option."""
    path, metrics = run
    return str(metrics.get("run_id") or path.parent.name)


def render_selected_pipeline_run(run_metrics: dict[str, Any]) -> None:
    """Render details for one selected pipeline run."""
    run_id = str(run_metrics.get("run_id") or "unknown")
    extraction = as_dict(run_metrics.get("extraction"))
    transformation = as_dict(run_metrics.get("transformation"))
    load = as_dict(run_metrics.get("load"))

    if extraction.get("sources_failed", 0):
        st.warning(
            "Medium priority: "
            f"{extraction['sources_failed']} source extraction(s) failed in this run."
        )

    st.subheader("Run Summary")
    st.json(
        {
            "run_id": run_id,
            "status": pipeline_run_status(run_metrics),
            "created_at": run_metrics.get("created_at"),
            "updated_at": run_metrics.get("updated_at"),
            "extracted_records": extraction.get("record_count"),
            "processed_records": transformation.get("total_records"),
            "staged_records": load.get("loaded_records"),
        },
        expanded=False,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### Extraction")
        st.json(extraction or {"status": "not available"}, expanded=False)
    with col2:
        st.markdown("### Transformation")
        st.json(transformation or {"status": "not available"}, expanded=False)
    with col3:
        st.markdown("### Staging Load")
        st.json(load or {"status": "not available"}, expanded=False)

    sources = extraction.get("sources")
    if isinstance(sources, list) and sources:
        st.subheader("Source-Level Extraction")
        st.dataframe(sources, width="stretch")


def render_aggregate_pipeline_runs(pipeline_runs: list[dict[str, Any]]) -> None:
    """Render aggregate execution metrics and one row per pipeline run."""
    aggregate = aggregate_pipeline_metrics(pipeline_runs)
    st.subheader("Aggregate Pipeline Metrics")
    columns = st.columns(6)
    columns[0].metric("Runs", aggregate["total_runs"])
    columns[1].metric("Complete runs", aggregate["complete_runs"])
    columns[2].metric("Extracted", aggregate["extracted_records"])
    columns[3].metric("Processed", aggregate["processed_records"])
    columns[4].metric("Staged", aggregate["loaded_records"])
    columns[5].metric("Source failures", aggregate["source_failures"])

    duration_metrics = {
        "average_extraction_duration_ms": aggregate["average_extraction_duration_ms"],
        "average_transformation_duration_ms": aggregate[
            "average_transformation_duration_ms"
        ],
        "average_load_duration_ms": aggregate["average_load_duration_ms"],
    }
    st.dataframe(flatten_metrics(duration_metrics), width="stretch")
    st.subheader("Metrics By Pipeline Run")
    st.dataframe(pipeline_run_rows(pipeline_runs), width="stretch")


def aggregate_pipeline_metrics(pipeline_runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate counters and stage durations across pipeline runs."""
    rows = pipeline_run_rows(pipeline_runs)
    return {
        "total_runs": len(rows),
        "complete_runs": sum(row["status"] == "complete" for row in rows),
        "extracted_records": sum_integer_column(rows, "extracted_records"),
        "processed_records": sum_integer_column(rows, "processed_records"),
        "loaded_records": sum_integer_column(rows, "loaded_records"),
        "source_failures": sum_integer_column(rows, "source_failures"),
        "average_extraction_duration_ms": average_numeric_column(
            rows, "extraction_duration_ms"
        ),
        "average_transformation_duration_ms": average_numeric_column(
            rows, "transformation_duration_ms"
        ),
        "average_load_duration_ms": average_numeric_column(rows, "load_duration_ms"),
    }


def pipeline_run_rows(pipeline_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten pipeline metrics into one summary row per run."""
    rows: list[dict[str, Any]] = []
    for metrics in pipeline_runs:
        extraction = as_dict(metrics.get("extraction"))
        transformation = as_dict(metrics.get("transformation"))
        load = as_dict(metrics.get("load"))
        rows.append(
            {
                "run_id": metrics.get("run_id") or "unknown",
                "status": pipeline_run_status(metrics),
                "created_at": metrics.get("created_at"),
                "updated_at": metrics.get("updated_at"),
                "extracted_records": integer_or_none(extraction.get("record_count")),
                "processed_records": integer_or_none(
                    transformation.get("total_records")
                ),
                "loaded_records": integer_or_none(load.get("loaded_records")),
                "source_failures": integer_or_none(extraction.get("sources_failed")),
                "extraction_duration_ms": extraction_duration_ms(extraction),
                "transformation_duration_ms": number_or_none(
                    transformation.get("duration_ms")
                ),
                "load_duration_ms": number_or_none(load.get("duration_ms")),
            }
        )
    return rows


def pipeline_run_status(metrics: dict[str, Any]) -> str:
    """Return whether all expected pipeline stage metrics are present."""
    stages = ("extraction", "transformation", "load")
    return (
        "complete"
        if all(as_dict(metrics.get(stage)) for stage in stages)
        else "incomplete"
    )


def extraction_duration_ms(extraction: dict[str, Any]) -> int | float | None:
    """Return extraction duration, deriving it from source metrics when needed."""
    duration = number_or_none(extraction.get("duration_ms"))
    if duration is not None:
        return duration
    sources = extraction.get("sources")
    if not isinstance(sources, list):
        return None
    durations = [
        source_duration
        for source in sources
        if isinstance(source, dict)
        and (source_duration := number_or_none(source.get("duration_ms"))) is not None
    ]
    return sum(durations) if durations else None


def sum_integer_column(rows: list[dict[str, Any]], key: str) -> int:
    """Sum integer values from summary rows, ignoring missing values."""
    return sum(value for row in rows if (value := row.get(key)) is not None)


def average_numeric_column(rows: list[dict[str, Any]], key: str) -> float | None:
    """Average numeric values from summary rows, ignoring missing values."""
    values = [value for row in rows if (value := row.get(key)) is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def render_samples_tab(
    database_url: str,
    database_metrics: dict[str, Any],
    database_error: str | None,
) -> None:
    """Render recent sample records directly from PostgreSQL."""
    if database_error:
        st.error(f"Database samples unavailable: {database_error}")
        return

    sources = sorted(as_dict(database_metrics.get("records_by_source")))
    source_filter = st.selectbox("Filter by source", ["all", *sources])
    try:
        records = query_database_samples(
            database_url, None if source_filter == "all" else source_filter
        )
    except DatabaseMetricsError as exc:
        st.error(f"Database samples unavailable: {exc}")
        return
    if not records:
        st.info("No records to display.")
        return
    st.caption("Showing up to 100 most recently loaded records.")
    st.dataframe([sample_record(record) for record in records], width="stretch")


def query_database_metrics(database_url: str) -> dict[str, Any]:
    """Query aggregate data-quality metrics from PostgreSQL."""
    try:
        import psycopg
    except ImportError as exc:
        msg = "Install psycopg[binary] or rebuild the dashboard image to query PostgreSQL."
        raise DatabaseMetricsError(msg) from exc

    try:
        with psycopg.connect(database_url) as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*),
                    COUNT(*) FILTER (WHERE jsonb_array_length(validation_errors) = 0),
                    COUNT(*) FILTER (WHERE is_multimodal = true),
                    COUNT(*) FILTER (WHERE record_type = 'article'),
                    COUNT(*) FILTER (
                        WHERE record_type = 'article' AND has_valid_image_url = true
                    ),
                    MAX(loaded_at)
                FROM news_records
                """
            )
            summary = cursor.fetchone()
            if summary is None:
                raise DatabaseMetricsError("Database summary query returned no rows.")

            cursor.execute(
                """
                SELECT extracted_from, COUNT(*)
                FROM news_records
                GROUP BY extracted_from
                ORDER BY COUNT(*) DESC
                """
            )
            records_by_source = dict(cursor.fetchall())
            cursor.execute(
                """
                SELECT record_type, COUNT(*)
                FROM news_records
                GROUP BY record_type
                ORDER BY COUNT(*) DESC
                """
            )
            records_by_type = dict(cursor.fetchall())
            cursor.execute(
                """
                SELECT error, COUNT(*)
                FROM news_records
                CROSS JOIN LATERAL
                    jsonb_array_elements_text(validation_errors) AS errors(error)
                GROUP BY error
                ORDER BY COUNT(*) DESC
                """
            )
            validation_errors = dict(cursor.fetchall())
    except psycopg.Error as exc:
        raise DatabaseMetricsError(str(exc)) from exc

    total_records = int(summary[0])
    valid_records = int(summary[1])
    multimodal_records = int(summary[2])
    article_records = int(summary[3])
    valid_article_image_records = int(summary[4])
    latest_loaded_at = summary[5]
    return {
        "total_records": total_records,
        "valid_records": valid_records,
        "valid_record_rate": calculate_percentage(valid_records, total_records),
        "multimodal_records": multimodal_records,
        "multimodal_rate": calculate_percentage(multimodal_records, total_records),
        "article_records": article_records,
        "valid_article_image_records": valid_article_image_records,
        "valid_article_image_rate": calculate_percentage(
            valid_article_image_records, article_records
        ),
        "invalid_or_missing_article_images": article_records
        - valid_article_image_records,
        "latest_loaded_at": latest_loaded_at.isoformat() if latest_loaded_at else None,
        "records_by_source": records_by_source,
        "records_by_type": records_by_type,
        "validation_errors": validation_errors,
    }


def query_database_samples(
    database_url: str, source_filter: str | None
) -> list[dict[str, Any]]:
    """Query a recent sample of records, optionally restricted by source."""
    try:
        import psycopg
    except ImportError as exc:
        msg = "Install psycopg[binary] or rebuild the dashboard image to query PostgreSQL."
        raise DatabaseMetricsError(msg) from exc

    query = """
        SELECT
            record_type,
            extracted_from,
            source_name,
            is_multimodal,
            validation_errors,
            text,
            loaded_at
        FROM news_records
    """
    parameters: tuple[str, ...] = ()
    if source_filter:
        query += " WHERE extracted_from = %s"
        parameters = (source_filter,)
    query += " ORDER BY loaded_at DESC LIMIT 100"

    try:
        with psycopg.connect(database_url) as conn, conn.cursor() as cursor:
            cursor.execute(query, parameters)
            rows = cursor.fetchall()
    except psycopg.Error as exc:
        raise DatabaseMetricsError(str(exc)) from exc

    columns = (
        "record_type",
        "extracted_from",
        "source_name",
        "is_multimodal",
        "validation_errors",
        "text",
        "loaded_at",
    )
    return [dict(zip(columns, row, strict=True)) for row in rows]


def render_count_chart(counts: Counter[str]) -> None:
    """Render a Streamlit bar chart and table for counts."""
    if not counts:
        st.info("No counts available.")
        return
    rows = [{"label": label, "count": count} for label, count in counts.most_common()]
    st.bar_chart(rows, x="label", y="count")
    st.dataframe(rows, width="stretch")


def flatten_metrics(metrics: dict[str, Any]) -> list[dict[str, str]]:
    """Flatten a metrics dictionary into display rows."""
    rows: list[dict[str, str]] = []
    for key, value in metrics.items():
        if isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False)
        rows.append({"metric": key, "value": str(value)})
    return rows


def sample_record(record: dict[str, Any]) -> dict[str, Any]:
    """Build a dashboard preview row for one database record."""
    loaded_at = record.get("loaded_at")
    return {
        "record_type": record.get("record_type"),
        "extracted_from": record.get("extracted_from"),
        "source_name": record.get("source_name"),
        "is_multimodal": record.get("is_multimodal"),
        "validation_errors": ", ".join(record.get("validation_errors") or []),
        "loaded_at": loaded_at.isoformat()
        if hasattr(loaded_at, "isoformat")
        else loaded_at,
        "text": shorten(record.get("text")),
    }


def shorten(value: object, max_length: int = 180) -> str:
    """Truncate a display value to a maximum length."""
    text = str(value or "")
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def format_percentage(value: object) -> str:
    """Format a numeric percentage for a metric card."""
    return f"{value}%" if isinstance(value, int | float) else "n/a"


def integer_or_none(value: object) -> int | None:
    """Return a non-boolean integer or None."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def number_or_none(value: object) -> int | float | None:
    """Return a non-boolean number or None."""
    return (
        value
        if isinstance(value, int | float) and not isinstance(value, bool)
        else None
    )


def as_dict(value: object) -> dict[str, Any]:
    """Return a dictionary value or an empty dictionary."""
    return value if isinstance(value, dict) else {}


def as_counter(value: object) -> Counter[str]:
    """Convert a dictionary-like count payload into a Counter."""
    if not isinstance(value, dict):
        return Counter()
    return Counter({str(key): int(count) for key, count in value.items()})


if __name__ == "__main__":
    main()
