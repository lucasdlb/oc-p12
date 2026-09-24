"""Transform raw source records into normalized processed records."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from news_ingestion.models import ProcessedRecord, RecordType
from news_ingestion.paths import ProjectPaths
from news_ingestion.persistence.json_artifacts import (
    read_json_object_array,
    write_json_atomically,
)
from news_ingestion.persistence.metrics import (
    calculate_processed_record_metrics,
    update_stage_metrics_file,
)
from news_ingestion.services.results import TransformResult
from news_ingestion.text import normalize_whitespace
from news_ingestion.url_validation import has_valid_image_url_format

logger = logging.getLogger(__name__)


def clean_text(value: Any) -> str:
    """Normalize arbitrary text values to a single-line stripped string."""
    return normalize_whitespace(value)


def normalize_list(value: Any) -> list[str]:
    """Normalize a scalar or list value into cleaned non-empty strings."""
    if value is None:
        return []
    if isinstance(value, list):
        values = value
    else:
        values = [value]
    return [cleaned for item in values if (cleaned := clean_text(item))]


def article_text(record: dict[str, Any]) -> str:
    """Combine article title, description, and content into text."""
    parts: list[str] = []
    for key in ("title", "description", "content"):
        part = clean_text(record.get(key))
        if part and part not in parts:
            parts.append(part)
    return "\n\n".join(parts)


def make_record_id(
    record_type: RecordType,
    extracted_from: str,
    source_record_id: str | None,
    fallback_identity: str,
) -> str:
    """Build a stable collision-resistant identifier from source identity."""
    identity = clean_text(source_record_id) or clean_text(fallback_identity)
    digest_input = f"{record_type}\0{extracted_from}\0{identity}".encode()
    digest = hashlib.sha256(digest_input).hexdigest()[:24]
    return f"{record_type}:{extracted_from}:{digest}"


def transform_article(record: dict[str, Any]) -> ProcessedRecord:
    """Transform one raw article dictionary into a processed record."""
    text = article_text(record)
    image_url = clean_text(record.get("image_url")) or None
    source_record_id = (
        clean_text(record.get("article_id")) or clean_text(record.get("link")) or None
    )
    extracted_from = clean_text(record.get("extracted_from")) or "unknown"
    has_valid_image_url = bool(image_url and has_valid_image_url_format(image_url))
    validation_errors: list[str] = []

    if not text:
        validation_errors.append("missing_text")
    if not image_url:
        validation_errors.append("missing_image_url")
    elif not has_valid_image_url:
        validation_errors.append("invalid_image_url_format")

    return ProcessedRecord(
        record_id=make_record_id(
            "article",
            extracted_from,
            source_record_id,
            "\0".join(
                (
                    text,
                    clean_text(record.get("published_at")),
                    clean_text(record.get("image_url")),
                )
            ),
        ),
        record_type="article",
        source_record_id=source_record_id,
        title=clean_text(record.get("title")) or None,
        text=text,
        image_url=image_url,
        source_url=clean_text(record.get("link")) or None,
        published_at=clean_text(record.get("published_at")) or None,
        source_name=clean_text(record.get("source_name")) or None,
        extracted_from=extracted_from,
        language=clean_text(record.get("language")) or None,
        country=normalize_list(record.get("country")),
        category=normalize_list(record.get("category")),
        label=_article_label(record),
        evidence_count=0,
        text_length=len(text),
        word_count=count_words(text),
        is_multimodal=bool(text and image_url),
        has_valid_image_url=has_valid_image_url,
        validation_errors=validation_errors,
    )


def transform_claim(record: dict[str, Any]) -> ProcessedRecord:
    """Transform one raw claim dictionary into a processed record."""
    text = clean_text(record.get("claim"))
    source_record_id = clean_text(record.get("claim_id")) or None
    extracted_from = clean_text(record.get("extracted_from")) or "unknown"
    evidence = record.get("evidence")
    validation_errors: list[str] = []

    if not text:
        validation_errors.append("missing_text")

    return ProcessedRecord(
        record_id=make_record_id(
            "claim",
            extracted_from,
            source_record_id,
            "\0".join((text, clean_text(record.get("label")))),
        ),
        record_type="claim",
        source_record_id=source_record_id,
        title=None,
        text=text,
        image_url=None,
        source_url=None,
        published_at=None,
        source_name=clean_text(record.get("source_name")) or None,
        extracted_from=extracted_from,
        language=clean_text(record.get("language")) or None,
        country=normalize_list(record.get("country")),
        category=[],
        label=clean_text(record.get("label")) or None,
        evidence_count=len(evidence) if isinstance(evidence, list) else 0,
        text_length=len(text),
        word_count=count_words(text),
        is_multimodal=False,
        has_valid_image_url=False,
        validation_errors=validation_errors,
    )


def transform_records(
    records: list[dict[str, Any]], record_type: RecordType
) -> list[ProcessedRecord]:
    """Transform raw records of one type into processed records."""
    transformer = transform_article if record_type == "article" else transform_claim
    return [transformer(record) for record in records]


def transform_raw_files_to_json(
    input_paths: Sequence[Path],
    output_path: Path,
    run_id: str | None = None,
    paths: ProjectPaths | None = None,
) -> TransformResult:
    """Transform explicit raw artifacts and commit processed records to JSON."""
    started_at = time.monotonic()
    processed_records: list[ProcessedRecord] = []

    for input_path in sorted(input_paths):
        record_type = infer_record_type_from_filename(input_path)
        if record_type is None:
            msg = f"Cannot infer record type from artifact name: {input_path.name}"
            raise ValueError(msg)

        raw_records = read_json_object_array(input_path)
        transformed = transform_records(raw_records, record_type)
        processed_records.extend(transformed)
        logger.info(
            "Transformed raw records",
            extra={
                "input_path": str(input_path),
                "record_type": record_type,
                "record_count": len(transformed),
            },
        )

    artifact_path = write_processed_records_json(processed_records, output_path)
    transformed_records = [record.to_dict() for record in processed_records]
    duration_ms = round((time.monotonic() - started_at) * 1000)
    metrics = {
        **calculate_processed_record_metrics(transformed_records),
        "input_paths": [str(path) for path in input_paths],
        "output_path": str(artifact_path),
        "duration_ms": duration_ms,
    }
    metrics_path = None
    if paths is not None:
        metrics_path = update_stage_metrics_file(
            "transformation", metrics, run_id, paths=paths
        )
    logger.info(
        "Saved processed records",
        extra={
            "output_path": str(artifact_path),
            "record_count": len(processed_records),
            "duration_ms": duration_ms,
            "metrics_path": str(metrics_path) if metrics_path else None,
            **metrics,
        },
    )
    return TransformResult(artifact_path, len(processed_records), duration_ms)


def infer_record_type_from_filename(input_path: Path) -> RecordType | None:
    """Infer a raw file record type from its filename."""
    file_name = input_path.name
    if file_name.endswith("_articles.json"):
        return "article"
    if file_name.endswith("_claims.json"):
        return "claim"
    return None


def write_processed_records_json(
    records: Sequence[ProcessedRecord], output_path: Path
) -> Path:
    """Atomically write processed records and return the committed path."""
    return write_json_atomically(
        [record.to_dict() for record in records],
        output_path,
    )


def count_words(text: str) -> int:
    """Count word-like tokens in text."""
    return len(re.findall(r"\b\w+\b", text))


def _article_label(record: dict[str, Any]) -> str | None:
    """Extract an optional article label from normalized or raw payload fields."""
    raw_payload = record.get("raw_payload")
    if isinstance(raw_payload, dict):
        for key in ("2_way_label", "3_way_label", "6_way_label", "label"):
            value = clean_text(raw_payload.get(key))
            if value:
                return value
    return clean_text(record.get("label")) or None
