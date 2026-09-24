"""Pure text normalization helpers shared across ingestion stages."""

import re
from collections.abc import Mapping
from typing import Any


def normalize_whitespace(value: object) -> str:
    """Convert a value to a stripped string with collapsed whitespace."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def coerce_nonempty_string(value: object) -> str | None:
    """Convert a value to a stripped non-empty string or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def first_nonempty_string(payload: Mapping[str, Any], *keys: str) -> str | None:
    """Return the first non-empty string value for candidate keys."""
    for key in keys:
        value = coerce_nonempty_string(payload.get(key))
        if value is not None:
            return value
    return None
