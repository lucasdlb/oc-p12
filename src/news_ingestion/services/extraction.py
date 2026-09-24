"""Generic source extraction orchestration."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from news_ingestion.config import Settings
from news_ingestion.models import RawArticle, RawClaim
from news_ingestion.paths import ProjectPaths
from news_ingestion.persistence.metrics import update_stage_metrics_file
from news_ingestion.services.results import (
    ExtractionBatchResult,
    SourceExtractionFailure,
    SourceExtractionResult,
)


@dataclass(frozen=True)
class SourceSpec[RecordT: (RawArticle, RawClaim)]:
    """Typed acquisition and persistence operations for one source."""

    name: str
    settings_key: str
    filename: str
    fetch_records: Callable[[Settings], list[RecordT]]
    write_records: Callable[[Sequence[RecordT], Path], Path]


AnySourceSpec = SourceSpec[RawArticle] | SourceSpec[RawClaim]


def extract_enabled_source_to_json[RecordT: (RawArticle, RawClaim)](
    source: SourceSpec[RecordT], settings: Settings, raw_dir: Path
) -> SourceExtractionResult:
    """Extract one enabled source into a committed JSON artifact."""
    if not _is_source_enabled(source, settings):
        msg = f"{source.name} extraction is disabled by configuration."
        raise RuntimeError(msg)
    return extract_source_to_json(source, settings, raw_dir)


def extract_source_to_json[RecordT: (RawArticle, RawClaim)](
    source: SourceSpec[RecordT], settings: Settings, raw_dir: Path
) -> SourceExtractionResult:
    """Acquire one source, atomically write it, and return result metadata."""
    requested_path = raw_dir / source.filename
    started_at = time.monotonic()
    logger = logging.getLogger(source.name)
    logger.info("Starting source extraction", extra={"source": source.name})
    records = source.fetch_records(settings)
    artifact_path = source.write_records(records, requested_path)
    duration_ms = round((time.monotonic() - started_at) * 1000)
    logger.info(
        "Committed source artifact",
        extra={
            "source": source.name,
            "record_count": len(records),
            "artifact_path": str(artifact_path),
            "duration_ms": duration_ms,
        },
    )
    return SourceExtractionResult(
        source=source.name,
        artifact_path=artifact_path,
        record_count=len(records),
        duration_ms=duration_ms,
    )


def extract_sources_to_json(
    sources: tuple[AnySourceSpec, ...],
    settings: Settings,
    raw_dir: Path,
    source_group: str,
    minimum_successes: int | None = None,
    minimum_records: int = 0,
    run_id: str | None = None,
    paths: ProjectPaths | None = None,
) -> ExtractionBatchResult:
    """Extract a source group and enforce source and record thresholds."""
    configured_source_count = len(sources)
    disabled_sources = [
        source.name for source in sources if not _is_source_enabled(source, settings)
    ]
    enabled_sources = tuple(
        source for source in sources if _is_source_enabled(source, settings)
    )
    minimum_successes = (
        len(enabled_sources) if minimum_successes is None else minimum_successes
    )
    if not enabled_sources:
        msg = f"No enabled {source_group} sources are configured."
        raise RuntimeError(msg)

    successful: list[SourceExtractionResult] = []
    failures: list[SourceExtractionFailure] = []
    for source in enabled_sources:
        started_at = time.monotonic()
        try:
            successful.append(extract_source_to_json(source, settings, raw_dir))
        except Exception as exc:
            duration_ms = round((time.monotonic() - started_at) * 1000)
            logging.getLogger(source.name).exception(
                "Extraction failed",
                extra={
                    "source": source.name,
                    "source_group": source_group,
                    "duration_ms": duration_ms,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            failures.append(
                SourceExtractionFailure(
                    source=source.name,
                    duration_ms=duration_ms,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )

    result = ExtractionBatchResult(tuple(successful), tuple(failures))
    extraction_metrics = {
        "source_group": source_group,
        "sources_configured": configured_source_count,
        "sources_enabled": len(enabled_sources),
        "sources_disabled": len(disabled_sources),
        "disabled_sources": disabled_sources,
        "sources_succeeded": len(successful),
        "sources_failed": len(failures),
        "failed_sources": [failure.source for failure in failures],
        "record_count": result.record_count,
        "minimum_successes": minimum_successes,
        "minimum_records": minimum_records,
        "sources": [
            {
                "source": source_result.source,
                "artifact_path": str(source_result.artifact_path),
                "record_count": source_result.record_count,
                "duration_ms": source_result.duration_ms,
                "error": None,
            }
            for source_result in successful
        ]
        + [
            {
                "source": failure.source,
                "artifact_path": None,
                "record_count": 0,
                "duration_ms": failure.duration_ms,
                "error": failure.error_message,
            }
            for failure in failures
        ],
    }
    metrics_path = (
        update_stage_metrics_file("extraction", extraction_metrics, run_id, paths=paths)
        if paths is not None
        else None
    )
    logging.getLogger(__name__).info(
        "Extraction source summary",
        extra={
            **extraction_metrics,
            "metrics_path": str(metrics_path) if metrics_path else None,
        },
    )

    if len(successful) < minimum_successes:
        msg = f"Fewer than {minimum_successes} {source_group} source extractions succeeded."
        raise RuntimeError(msg)
    if result.record_count < minimum_records:
        msg = (
            f"{source_group.capitalize()} extraction produced {result.record_count} "
            f"records; at least {minimum_records} required."
        )
        raise RuntimeError(msg)
    if failures:
        logging.getLogger(__name__).warning(
            "Extraction completed with partial source failures",
            extra={
                "source_group": source_group,
                "failed_sources": [failure.source for failure in failures],
            },
        )
    return result


def extract_named_source_to_json(
    name: str,
    sources: tuple[AnySourceSpec, ...],
    raw_dir: Path,
    settings: Settings,
) -> SourceExtractionResult:
    """Extract one configured source by name."""
    for source in sources:
        if source.name == name:
            return extract_enabled_source_to_json(source, settings, raw_dir)
    msg = f"Unknown source: {name}"
    raise ValueError(msg)


def _is_source_enabled[RecordT: (RawArticle, RawClaim)](
    source: SourceSpec[RecordT], settings: Settings
) -> bool:
    """Return whether a source is enabled by its settings section."""
    source_settings = getattr(settings, source.settings_key)
    return bool(source_settings.enabled)
