"""HTTP request helpers shared by source clients."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


def get_json_with_retries(
    source: str,
    url: str,
    params: dict[str, str],
    timeout: int,
    max_retries: int,
    retry_backoff_seconds: list[int],
    logger: logging.Logger,
) -> dict[str, Any]:
    """Fetch a JSON object with retry handling for transient HTTP failures."""
    attempts = max_retries + 1
    last_exception: requests.RequestException | ValueError | TypeError | None = None

    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                msg = f"{source} response JSON root was not an object."
                raise TypeError(msg)
            return payload
        except requests.RequestException as exc:
            last_exception = exc
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            if not _should_retry(status_code, attempt, max_retries):
                _log_request_failure(
                    logger, source, exc, attempt, max_retries, status_code
                )
                msg = f"{source} HTTP request failed."
                raise RuntimeError(msg) from exc

            retry_after = _retry_after_seconds(response)
            retry_delay = (
                retry_after
                if retry_after is not None
                else _retry_delay(attempt, retry_backoff_seconds)
            )
            logger.warning(
                "%s HTTP request will be retried",
                source,
                extra={
                    "source": source.lower(),
                    "status_code": status_code,
                    "retry_attempt": attempt,
                    "max_retries": max_retries,
                    "retry_delay_seconds": retry_delay,
                    "retry_after": retry_after,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            time.sleep(retry_delay)
        except (TypeError, ValueError) as exc:
            last_exception = exc
            msg = f"{source} response was not valid JSON."
            raise RuntimeError(msg) from exc

    msg = f"{source} HTTP request failed."
    raise RuntimeError(msg) from last_exception


def _should_retry(status_code: int | None, attempt: int, max_retries: int) -> bool:
    """Return whether a request should be retried for the status and attempt."""
    return status_code in TRANSIENT_STATUS_CODES and attempt <= max_retries


def _retry_delay(attempt: int, retry_backoff_seconds: list[int]) -> int:
    """Return the configured retry delay for an attempt."""
    if not retry_backoff_seconds:
        return 0
    index = min(attempt - 1, len(retry_backoff_seconds) - 1)
    return retry_backoff_seconds[index]


def _retry_after_seconds(response: requests.Response | None) -> int | None:
    """Parse a non-negative Retry-After delay from a response."""
    if response is None:
        return None
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return None
    try:
        delay = int(retry_after)
    except ValueError:
        return None
    return max(delay, 0)


def _log_request_failure(
    logger: logging.Logger,
    source: str,
    exc: requests.RequestException,
    attempt: int,
    max_retries: int,
    status_code: int | None,
) -> None:
    """Log details for a failed HTTP request."""
    logger.warning(
        "%s HTTP request failed",
        source,
        extra={
            "source": source.lower(),
            "status_code": status_code,
            "attempts": attempt,
            "max_retries": max_retries,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        },
    )
