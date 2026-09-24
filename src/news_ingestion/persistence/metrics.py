"""Metric calculation and persistence helpers for pipeline runs."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from news_ingestion.config import get_settings
from news_ingestion.paths import ProjectPaths, project_paths
from news_ingestion.persistence.json_artifacts import write_json_atomically


def metrics_output_path(
    run_id: str | None = None,
    paths: ProjectPaths | None = None,
) -> Path:
    """Return the metrics output path for a run or the latest run."""
    resolved_paths = paths or project_paths(get_settings())
    return resolved_paths.metrics_output_path(run_id)


def load_metrics_or_empty(path: Path) -> dict[str, Any]:
    """Load a metrics JSON object, returning an empty object if absent."""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Expected {path} to contain a JSON object."
        raise TypeError(msg)
    return payload


def update_stage_metrics_file(
    stage: str,
    metrics: dict[str, Any],
    run_id: str | None = None,
    path: Path | None = None,
    paths: ProjectPaths | None = None,
) -> Path:
    """Save metrics for a pipeline stage and return the written path."""
    output_path = path or metrics_output_path(run_id, paths)
    payload = load_metrics_or_empty(output_path)
    updated_at = datetime.now(UTC).isoformat()
    payload[stage] = metrics
    payload.setdefault("created_at", updated_at)
    payload["updated_at"] = updated_at
    if run_id:
        payload["run_id"] = run_id
        record_count = _stage_record_count(metrics)
        if record_count is not None:
            records_by_run = payload.setdefault("records_by_run", {})
            if not isinstance(records_by_run, dict):
                records_by_run = {}
                payload["records_by_run"] = records_by_run
            records_by_run[run_id] = record_count

    return write_json_atomically(payload, output_path)


def _stage_record_count(metrics: dict[str, Any]) -> int | None:
    """Return the primary record count reported by a pipeline stage."""
    for key in ("loaded_records", "total_records", "record_count"):
        value = metrics.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def calculate_processed_record_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate aggregate quality metrics for processed records."""
    total_records = len(records)
    article_records = [
        record for record in records if record.get("record_type") == "article"
    ]
    valid_records = [
        record for record in records if not record.get("validation_errors")
    ]
    multimodal_records = [record for record in records if record.get("is_multimodal")]
    valid_image_records = [
        record for record in article_records if record.get("has_valid_image_url")
    ]

    validation_counts: Counter[str] = Counter()
    for record in records:
        errors = record.get("validation_errors")
        if isinstance(errors, list):
            validation_counts.update(str(error) for error in errors)

    return {
        "total_records": total_records,
        "article_records": len(article_records),
        "claim_records": sum(
            1 for record in records if record.get("record_type") == "claim"
        ),
        "valid_records": len(valid_records),
        "valid_record_rate": calculate_percentage(len(valid_records), total_records),
        "multimodal_records": len(multimodal_records),
        "multimodal_rate": calculate_percentage(len(multimodal_records), total_records),
        "valid_article_image_records": len(valid_image_records),
        "valid_article_image_rate": calculate_percentage(
            len(valid_image_records), len(article_records)
        ),
        "invalid_or_missing_article_images": len(article_records)
        - len(valid_image_records),
        "records_by_source": dict(
            Counter(
                str(record.get("extracted_from") or "unknown") for record in records
            )
        ),
        "records_by_type": dict(
            Counter(str(record.get("record_type") or "unknown") for record in records)
        ),
        "validation_errors": dict(validation_counts),
    }


def calculate_percentage(numerator: int, denominator: int) -> float:
    """Return a rounded percentage, or zero for an empty denominator."""
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)
