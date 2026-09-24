"""Processed-record loading use cases."""

import logging
import time
from pathlib import Path
from typing import Any

from news_ingestion.paths import ProjectPaths
from news_ingestion.persistence.json_artifacts import read_json_object_array
from news_ingestion.persistence.metrics import (
    calculate_processed_record_metrics,
    update_stage_metrics_file,
)
from news_ingestion.persistence.postgres import replace_staging_records

logger = logging.getLogger(__name__)


def load_processed_records_to_staging(
    processed_path: Path,
    conn: Any,
    run_id: str,
    paths: ProjectPaths | None = None,
) -> int:
    """Load one processed artifact into run-scoped PostgreSQL staging."""
    started_at = time.monotonic()
    records = read_json_object_array(processed_path)
    loaded_records = replace_staging_records(records, conn, run_id)
    duration_ms = round((time.monotonic() - started_at) * 1000)
    load_metrics = {
        "processed_path": str(processed_path),
        "table": "news_records_staging",
        "loaded_records": loaded_records,
        "duration_ms": duration_ms,
        "loaded_data_quality": calculate_processed_record_metrics(records),
    }
    metrics_path = update_stage_metrics_file("load", load_metrics, run_id, paths=paths)
    logger.info(
        "Loaded processed records to staging table",
        extra={
            **load_metrics,
            "record_count": loaded_records,
            "metrics_path": str(metrics_path),
        },
    )
    return loaded_records
