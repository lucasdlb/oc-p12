"""PostgreSQL persistence for processed news records."""

from __future__ import annotations

import json
from typing import Any

from news_ingestion.models import PROCESSED_RECORD_COLUMNS

RECORD_COLUMNS = PROCESSED_RECORD_COLUMNS


def replace_staging_records(
    records: list[dict[str, Any]],
    conn: Any,
    run_id: str,
) -> int:
    """Replace one run's PostgreSQL staging rows and return their count."""
    rows = [(run_id, *_record_to_row(record)) for record in records]
    with conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM news_records_staging WHERE run_id = %s",
            (run_id,),
        )
    if not rows:
        conn.commit()
        return 0

    query = f"""
        INSERT INTO news_records_staging (run_id, {", ".join(RECORD_COLUMNS)})
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s::jsonb
        )
    """
    with conn.cursor() as cursor:
        cursor.executemany(query, rows)
    conn.commit()
    return len(rows)


def _record_to_row(record: object) -> tuple[Any, ...]:
    """Convert one processed record object to a database row tuple."""
    if not isinstance(record, dict):
        msg = "Expected every processed record to be a JSON object."
        raise TypeError(msg)

    return tuple(_record_value(record, column) for column in RECORD_COLUMNS)


def _record_value(record: dict[str, Any], column: str) -> Any:
    """Return the database-ready value for a processed record column."""
    value = record.get(column)
    if column in {"country", "category", "validation_errors"}:
        return json.dumps(value or [])
    if column == "source_name":
        return value or "unknown"
    return value
