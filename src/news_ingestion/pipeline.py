from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from news_ingestion.climate_fever_client import ClimateFeverClient
from news_ingestion.config import Settings, get_settings
from news_ingestion.dataforgood_client import DataForGoodClient
from news_ingestion.fakeddit_client import FakedditClient
from news_ingestion.gdelt_client import GdeltClient
from news_ingestion.models import RawArticle, RawClaim
from news_ingestion.newsdata_client import NewsDataClient
from news_ingestion.rss_client import RssClient
from news_ingestion.script_utils import (
    default_airflow_run_id,
    live_raw_dir,
    processed_output_path,
    run_article_extraction,
    run_claim_extraction,
    static_processed_output_path,
    static_raw_dir,
)
from news_ingestion.transformation import transform_raw_directory

RecordKind = Literal["article", "claim"]


@dataclass(frozen=True)
class SourceSpec:
    name: str
    filename: str
    record_kind: RecordKind
    fetch_records: Callable[[Settings], list[RawArticle] | list[RawClaim]]


@dataclass(frozen=True)
class SourceFetchResult:
    source: str
    output_path: Path | None
    record_count: int
    duration_ms: int
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


LIVE_SOURCES = (
    SourceSpec(
        name="newsdata",
        filename="newsdata_articles.json",
        record_kind="article",
        fetch_records=lambda settings: NewsDataClient.from_settings(
            settings
        ).fetch_articles(),
    ),
    SourceSpec(
        name="gdelt",
        filename="gdelt_articles.json",
        record_kind="article",
        fetch_records=lambda settings: GdeltClient.from_settings(
            settings
        ).fetch_articles(),
    ),
    SourceSpec(
        name="rss",
        filename="rss_articles.json",
        record_kind="article",
        fetch_records=lambda settings: RssClient.from_settings(
            settings
        ).fetch_articles(),
    ),
)

STATIC_SOURCES = (
    SourceSpec(
        name="fakeddit",
        filename="fakeddit_articles.json",
        record_kind="article",
        fetch_records=lambda settings: FakedditClient.from_settings(
            settings
        ).fetch_articles(),
    ),
    SourceSpec(
        name="climate_fever",
        filename="climate_fever_claims.json",
        record_kind="claim",
        fetch_records=lambda settings: ClimateFeverClient.from_settings(
            settings
        ).fetch_claims(),
    ),
    SourceSpec(
        name="dataforgood",
        filename="dataforgood_claims.json",
        record_kind="claim",
        fetch_records=lambda settings: DataForGoodClient.from_settings(
            settings
        ).fetch_claims(),
    ),
)


def resolve_run_id(run_id: str | None = None) -> str | None:
    return run_id or default_airflow_run_id()


def source_output_path(source: SourceSpec, raw_dir: Path) -> Path:
    return raw_dir / source.filename


def fetch_source(
    source: SourceSpec, settings: Settings, raw_dir: Path
) -> SourceFetchResult:
    output_path = source_output_path(source, raw_dir)
    started_at = time.monotonic()
    if source.record_kind == "article":
        records = run_article_extraction(
            source.name,
            lambda: cast(list[RawArticle], source.fetch_records(settings)),
            output_path,
        )
    else:
        records = run_claim_extraction(
            source.name,
            lambda: cast(list[RawClaim], source.fetch_records(settings)),
            output_path,
        )
    return SourceFetchResult(
        source=source.name,
        output_path=output_path,
        record_count=len(records),
        duration_ms=round((time.monotonic() - started_at) * 1000),
    )


def fetch_sources(
    sources: tuple[SourceSpec, ...],
    settings: Settings,
    raw_dir: Path,
    source_group: str,
    minimum_successes: int | None = None,
) -> list[Path]:
    minimum_successes = len(sources) if minimum_successes is None else minimum_successes
    results: list[SourceFetchResult] = []

    for source in sources:
        started_at = time.monotonic()
        try:
            results.append(fetch_source(source, settings, raw_dir))
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
            results.append(
                SourceFetchResult(
                    source=source.name,
                    output_path=None,
                    record_count=0,
                    duration_ms=duration_ms,
                    error=str(exc),
                )
            )

    successful_results = [result for result in results if result.succeeded]
    failed_results = [result for result in results if not result.succeeded]
    output_paths = [
        result.output_path for result in successful_results if result.output_path
    ]

    logging.getLogger(__name__).info(
        "Extraction source summary",
        extra={
            "source_group": source_group,
            "sources_total": len(sources),
            "sources_succeeded": len(successful_results),
            "sources_failed": len(failed_results),
            "failed_sources": [result.source for result in failed_results],
            "record_count": sum(result.record_count for result in successful_results),
            "minimum_successes": minimum_successes,
        },
    )

    if len(successful_results) < minimum_successes:
        logging.getLogger(__name__).error(
            "Extraction failed below minimum success threshold",
            extra={
                "source_group": source_group,
                "sources_succeeded": len(successful_results),
                "sources_failed": len(failed_results),
                "failed_sources": [result.source for result in failed_results],
                "minimum_successes": minimum_successes,
            },
        )
        msg = f"Fewer than {minimum_successes} {source_group} source extractions succeeded."
        raise RuntimeError(msg)

    if failed_results:
        logging.getLogger(__name__).warning(
            "Extraction completed with partial source failures",
            extra={
                "source_group": source_group,
                "failed_sources": [result.source for result in failed_results],
            },
        )
    else:
        logging.getLogger(__name__).info(
            "Extraction completed successfully",
            extra={"source_group": source_group},
        )

    return output_paths


def fetch_newsdata(run_id: str | None = None, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    raw_dir = live_raw_dir(settings, resolve_run_id(run_id))
    result = fetch_source(LIVE_SOURCES[0], settings, raw_dir)
    if result.output_path is None:
        msg = "NewsData.io extraction did not produce an output path."
        raise RuntimeError(msg)
    return result.output_path


def fetch_gdelt(run_id: str | None = None, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    if not settings.gdelt.enabled:
        msg = "GDELT extraction is disabled by configuration."
        raise RuntimeError(msg)
    raw_dir = live_raw_dir(settings, resolve_run_id(run_id))
    result = fetch_source(LIVE_SOURCES[1], settings, raw_dir)
    if result.output_path is None:
        msg = "GDELT extraction did not produce an output path."
        raise RuntimeError(msg)
    return result.output_path


def fetch_rss(run_id: str | None = None, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    raw_dir = live_raw_dir(settings, resolve_run_id(run_id))
    result = fetch_source(LIVE_SOURCES[2], settings, raw_dir)
    if result.output_path is None:
        msg = "RSS extraction did not produce an output path."
        raise RuntimeError(msg)
    return result.output_path


def fetch_live_sources(run_id: str | None = None) -> list[Path]:
    settings = get_settings()
    resolved_run_id = resolve_run_id(run_id)
    raw_dir = live_raw_dir(settings, resolved_run_id)
    live_sources = tuple(
        source
        for source in LIVE_SOURCES
        if source.name != "gdelt" or settings.gdelt.enabled
    )
    return fetch_sources(live_sources, settings, raw_dir, "live", minimum_successes=1)


def fetch_fakeddit(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    result = fetch_source(STATIC_SOURCES[0], settings, static_raw_dir(settings))
    if result.output_path is None:
        msg = "Fakeddit extraction did not produce an output path."
        raise RuntimeError(msg)
    return result.output_path


def fetch_climate_fever(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    result = fetch_source(STATIC_SOURCES[1], settings, static_raw_dir(settings))
    if result.output_path is None:
        msg = "Climate-FEVER extraction did not produce an output path."
        raise RuntimeError(msg)
    return result.output_path


def fetch_dataforgood(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    result = fetch_source(STATIC_SOURCES[2], settings, static_raw_dir(settings))
    if result.output_path is None:
        msg = "DataForGood extraction did not produce an output path."
        raise RuntimeError(msg)
    return result.output_path


def fetch_static_sources() -> list[Path]:
    settings = get_settings()
    return fetch_sources(STATIC_SOURCES, settings, static_raw_dir(settings), "static")


def transform_live_run(run_id: str | None = None) -> Path:
    settings = get_settings()
    resolved_run_id = resolve_run_id(run_id)
    output_path = processed_output_path(settings, resolved_run_id)
    transform_raw_directory(live_raw_dir(settings, resolved_run_id), output_path)
    return output_path


def transform_static_sources() -> Path:
    settings = get_settings()
    output_path = static_processed_output_path(settings)
    transform_raw_directory(static_raw_dir(settings), output_path)
    return output_path
