"""JSON artifact persistence helpers."""

import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from news_ingestion.models import RawArticle, RawClaim


def read_json_object_array(input_path: Path) -> list[dict[str, Any]]:
    """Read and validate a JSON array of objects."""
    records = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        msg = f"Expected {input_path} to contain a JSON array."
        raise TypeError(msg)
    if any(not isinstance(record, dict) for record in records):
        msg = f"Expected every record in {input_path} to be a JSON object."
        raise TypeError(msg)
    return records


def write_raw_articles_json(articles: Sequence[RawArticle], output_path: Path) -> Path:
    """Atomically write raw article records and return the committed path."""
    return write_json_atomically(
        [article.to_dict() for article in articles], output_path
    )


def write_raw_claims_json(claims: Sequence[RawClaim], output_path: Path) -> Path:
    """Atomically write raw claim records and return the committed path."""
    return write_json_atomically([claim.to_dict() for claim in claims], output_path)


def write_json_atomically(payload: Any, output_path: Path) -> Path:
    """Atomically replace a JSON artifact after writing it completely."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        mode = output_path.stat().st_mode & 0o777 if output_path.exists() else 0o644
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
            os.fchmod(file.fileno(), mode)
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        temporary_path.replace(output_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return output_path
