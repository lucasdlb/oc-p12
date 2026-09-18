from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from news_ingestion.config import PROJECT_ROOT
from news_ingestion.script_utils import safe_run_id

METRICS_ROOT = PROJECT_ROOT / "data" / "metrics"


def metrics_output_path(run_id: str | None = None) -> Path:
    if run_id:
        return METRICS_ROOT / "runs" / safe_run_id(run_id) / "metrics.json"
    return METRICS_ROOT / "metrics.json"


def load_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Expected {path} to contain a JSON object."
        raise TypeError(msg)
    return payload


def save_stage_metrics(
    stage: str,
    metrics: dict[str, Any],
    run_id: str | None = None,
    path: Path | None = None,
) -> Path:
    output_path = path or metrics_output_path(run_id)
    payload = load_metrics(output_path)
    payload[stage] = metrics
    payload["updated_at"] = datetime.now(UTC).isoformat()
    if run_id:
        payload["run_id"] = run_id

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def processed_record_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
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
        "valid_record_rate": percentage(len(valid_records), total_records),
        "multimodal_records": len(multimodal_records),
        "multimodal_rate": percentage(len(multimodal_records), total_records),
        "valid_article_image_records": len(valid_image_records),
        "valid_article_image_rate": percentage(
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


def percentage(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def infer_run_id_from_processed_path(processed_path: Path) -> str | None:
    parts = processed_path.parts
    if "runs" not in parts:
        return None
    run_index = parts.index("runs")
    if run_index + 1 >= len(parts):
        return None
    return parts[run_index + 1]


def latest_metrics_path(metrics_root: Path = METRICS_ROOT) -> Path | None:
    candidates = list(metrics_root.glob("metrics.json"))
    candidates.extend(metrics_root.glob("runs/*/metrics.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)
