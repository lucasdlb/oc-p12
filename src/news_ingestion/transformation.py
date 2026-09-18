from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from news_ingestion.config import PROJECT_ROOT
from news_ingestion.image_validation import has_valid_image_url_format
from news_ingestion.metrics import processed_record_metrics, save_stage_metrics

logger = logging.getLogger(__name__)

RecordType = Literal["article", "claim"]


@dataclass(frozen=True)
class ProcessedRecord:
    record_id: str
    record_type: RecordType
    source_record_id: str | None
    title: str | None
    text: str
    image_url: str | None
    source_url: str | None
    published_at: str | None
    source_name: str | None
    extracted_from: str
    language: str | None
    country: list[str]
    category: list[str]
    label: str | None
    evidence_count: int
    text_length: int
    word_count: int
    is_multimodal: bool
    has_valid_image_url: bool
    validation_errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        values = value
    else:
        values = [value]
    return [cleaned for item in values if (cleaned := clean_text(item))]


def article_text(record: dict[str, Any]) -> str:
    parts = [
        clean_text(record.get("title")),
        clean_text(record.get("description")),
        clean_text(record.get("content")),
    ]
    return "\n\n".join(part for part in parts if part)


def make_record_id(
    record_type: RecordType,
    extracted_from: str,
    source_record_id: str | None,
    index: int,
) -> str:
    stable_id = clean_text(source_record_id) or f"row-{index}"
    safe_id = re.sub(r"[^A-Za-z0-9_.:-]+", "-", stable_id).strip("-")
    return f"{record_type}:{extracted_from}:{safe_id}"


def transform_article(record: dict[str, Any], index: int) -> ProcessedRecord:
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
        record_id=make_record_id("article", extracted_from, source_record_id, index),
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


def transform_claim(record: dict[str, Any], index: int) -> ProcessedRecord:
    text = clean_text(record.get("claim"))
    source_record_id = clean_text(record.get("claim_id")) or None
    extracted_from = clean_text(record.get("extracted_from")) or "unknown"
    evidence = record.get("evidence")
    validation_errors: list[str] = []

    if not text:
        validation_errors.append("missing_text")

    return ProcessedRecord(
        record_id=make_record_id("claim", extracted_from, source_record_id, index),
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
    transformer = transform_article if record_type == "article" else transform_claim
    return [transformer(record, index) for index, record in enumerate(records, start=1)]


def transform_raw_directory(
    raw_data_dir: Path = PROJECT_ROOT / "data" / "raw" / "live",
    output_path: Path = PROJECT_ROOT / "data" / "processed" / "processed_records.json",
    run_id: str | None = None,
) -> list[ProcessedRecord]:
    started_at = time.monotonic()
    processed_records: list[ProcessedRecord] = []

    for input_path in sorted(raw_data_dir.glob("*.json")):
        record_type = infer_record_type(input_path)
        if record_type is None:
            logger.info(
                "Skipping file because record type is unknown",
                extra={"input_path": str(input_path)},
            )
            continue

        raw_records = load_json_records(input_path)
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

    save_processed_records(processed_records, output_path)
    transformed_records = [record.to_dict() for record in processed_records]
    metrics = {
        **processed_record_metrics(transformed_records),
        "input_dir": str(raw_data_dir),
        "output_path": str(output_path),
        "duration_ms": round((time.monotonic() - started_at) * 1000),
    }
    metrics_path = save_stage_metrics("transformation", metrics, run_id)
    logger.info(
        "Saved processed records",
        extra={
            "output_path": str(output_path),
            "record_count": len(processed_records),
            "duration_ms": metrics["duration_ms"],
            "metrics_path": str(metrics_path),
            **metrics,
        },
    )
    return processed_records


def infer_record_type(input_path: Path) -> RecordType | None:
    file_name = input_path.name
    if file_name.endswith("_articles.json"):
        return "article"
    if file_name.endswith("_claims.json"):
        return "claim"
    return None


def load_json_records(input_path: Path) -> list[dict[str, Any]]:
    records = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        msg = f"Expected {input_path} to contain a JSON array."
        raise TypeError(msg)
    invalid_records = [record for record in records if not isinstance(record, dict)]
    if invalid_records:
        msg = f"Expected every record in {input_path} to be a JSON object."
        raise TypeError(msg)
    return records


def save_processed_records(records: list[ProcessedRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            [record.to_dict() for record in records], ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _article_label(record: dict[str, Any]) -> str | None:
    raw_payload = record.get("raw_payload")
    if isinstance(raw_payload, dict):
        for key in ("2_way_label", "3_way_label", "6_way_label", "label"):
            value = clean_text(raw_payload.get(key))
            if value:
                return value
    return clean_text(record.get("label")) or None
