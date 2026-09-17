from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from datetime import UTC, datetime
from typing import Any

RESERVED_LOG_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        for key, value in record.__dict__.items():
            if key not in RESERVED_LOG_RECORD_KEYS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["error_detail"] = "".join(
                traceback.format_exception(*record.exc_info)
            )

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(log_level: str | None = None) -> None:
    level_name = (log_level or os.getenv("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = JsonFormatter()
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if root_logger.handlers:
        for handler in root_logger.handlers:
            handler.setLevel(level)
            handler.setFormatter(formatter)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
