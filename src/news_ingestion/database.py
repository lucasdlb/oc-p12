from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RECORD_COLUMNS = (
    "record_id",
    "record_type",
    "source_record_id",
    "title",
    "text",
    "image_url",
    "source_url",
    "published_at",
    "source_name",
    "extracted_from",
    "language",
    "country",
    "category",
    "label",
    "evidence_count",
    "text_length",
    "word_count",
    "is_multimodal",
    "has_valid_image_url",
    "validation_errors",
)


def load_processed_records_to_temp(processed_path: Path, conn: Any) -> int:
    records = json.loads(processed_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        msg = f"Expected {processed_path} to contain a JSON array."
        raise TypeError(msg)

    rows = [_record_to_row(record) for record in records]
    if not rows:
        return 0

    query = f"""
        INSERT INTO news_records_temp ({", ".join(RECORD_COLUMNS)})
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s::jsonb
        )
    """
    with conn.cursor() as cursor:
        cursor.executemany(query, rows)
    conn.commit()
    return len(rows)


def _record_to_row(record: object) -> tuple[Any, ...]:
    if not isinstance(record, dict):
        msg = "Expected every processed record to be a JSON object."
        raise TypeError(msg)

    return tuple(_record_value(record, column) for column in RECORD_COLUMNS)


def _record_value(record: dict[str, Any], column: str) -> Any:
    value = record.get(column)
    if column in {"country", "category", "validation_errors"}:
        return json.dumps(value or [])
    if column == "source_name":
        return value or "unknown"
    return value
