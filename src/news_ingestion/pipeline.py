from __future__ import annotations

import logging
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


def fetch_source(source: SourceSpec, settings: Settings, raw_dir: Path) -> Path:
    output_path = source_output_path(source, raw_dir)
    if source.record_kind == "article":
        run_article_extraction(
            source.name,
            lambda: cast(list[RawArticle], source.fetch_records(settings)),
            output_path,
        )
    else:
        run_claim_extraction(
            source.name,
            lambda: cast(list[RawClaim], source.fetch_records(settings)),
            output_path,
        )
    return output_path


def fetch_sources(
    sources: tuple[SourceSpec, ...],
    settings: Settings,
    raw_dir: Path,
    source_group: str,
) -> list[Path]:
    output_paths: list[Path] = []
    failed_sources: list[str] = []

    for source in sources:
        try:
            output_paths.append(fetch_source(source, settings, raw_dir))
        except Exception:
            logging.getLogger(source.name).exception("Extraction failed")
            failed_sources.append(source.name)

    if failed_sources:
        logging.getLogger(__name__).error(
            "Extraction completed with failed sources: %s",
            ", ".join(failed_sources),
        )
        msg = f"One or more {source_group} source extractions failed."
        raise RuntimeError(msg)

    logging.getLogger(__name__).info("Extraction completed successfully")
    return output_paths


def fetch_newsdata(run_id: str | None = None, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    raw_dir = live_raw_dir(settings, resolve_run_id(run_id))
    return fetch_source(LIVE_SOURCES[0], settings, raw_dir)


def fetch_gdelt(run_id: str | None = None, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    raw_dir = live_raw_dir(settings, resolve_run_id(run_id))
    return fetch_source(LIVE_SOURCES[1], settings, raw_dir)


def fetch_rss(run_id: str | None = None, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    raw_dir = live_raw_dir(settings, resolve_run_id(run_id))
    return fetch_source(LIVE_SOURCES[2], settings, raw_dir)


def fetch_live_sources(run_id: str | None = None) -> list[Path]:
    settings = get_settings()
    resolved_run_id = resolve_run_id(run_id)
    raw_dir = live_raw_dir(settings, resolved_run_id)
    return fetch_sources(LIVE_SOURCES, settings, raw_dir, "live")


def fetch_fakeddit(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return fetch_source(STATIC_SOURCES[0], settings, static_raw_dir(settings))


def fetch_climate_fever(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return fetch_source(STATIC_SOURCES[1], settings, static_raw_dir(settings))


def fetch_dataforgood(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return fetch_source(STATIC_SOURCES[2], settings, static_raw_dir(settings))


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
