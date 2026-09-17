from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from news_ingestion.config import Settings
from news_ingestion.logging_config import configure_logging as configure_json_logging
from news_ingestion.models import RawArticle, RawClaim
from news_ingestion.storage import save_raw_articles, save_raw_claims


def default_airflow_run_id() -> str | None:
    return os.getenv("AIRFLOW_CTX_DAG_RUN_ID")


def safe_run_id(run_id: str) -> str:
    cleaned_run_id = re.sub(r"[^A-Za-z0-9_.=-]+", "_", run_id.strip())
    return cleaned_run_id.strip("_") or "manual"


def live_raw_dir(settings: Settings, run_id: str | None = None) -> Path:
    base_dir = settings.raw_data_dir / "live"
    if run_id:
        return base_dir / "runs" / safe_run_id(run_id)
    return base_dir


def static_raw_dir(settings: Settings) -> Path:
    return settings.raw_data_dir / "static"


def processed_output_path(settings: Settings, run_id: str | None = None) -> Path:
    if run_id:
        return (
            settings.processed_data_dir
            / "runs"
            / safe_run_id(run_id)
            / "processed_records.json"
        )
    return settings.processed_data_dir / "processed_records.json"


def static_processed_output_path(settings: Settings) -> Path:
    return settings.processed_data_dir / "static" / "processed_records.json"


def configure_logging() -> None:
    configure_json_logging()


def run_article_extraction(
    source_name: str,
    fetch: Callable[[], list[RawArticle]],
    output_path: Path,
) -> list[RawArticle]:
    import logging

    logger = logging.getLogger(source_name)
    started_at = time.monotonic()
    logger.info("Starting article extraction", extra={"source": source_name})
    articles = fetch()
    save_raw_articles(articles, output_path)
    logger.info(
        "Saved articles",
        extra={
            "source": source_name,
            "record_count": len(articles),
            "output_path": str(output_path),
            "duration_ms": round((time.monotonic() - started_at) * 1000),
        },
    )
    return articles


def run_claim_extraction(
    source_name: str,
    fetch: Callable[[], list[RawClaim]],
    output_path: Path,
) -> list[RawClaim]:
    import logging

    logger = logging.getLogger(source_name)
    started_at = time.monotonic()
    logger.info("Starting claim extraction", extra={"source": source_name})
    claims = fetch()
    save_raw_claims(claims, output_path)
    logger.info(
        "Saved claims",
        extra={
            "source": source_name,
            "record_count": len(claims),
            "output_path": str(output_path),
            "duration_ms": round((time.monotonic() - started_at) * 1000),
        },
    )
    return claims


def run_sources(sources: Sequence[tuple[str, Callable[[], object]]]) -> int:
    import logging

    failed_sources: list[str] = []

    for source_name, run_source in sources:
        try:
            run_source()
        except Exception:
            logging.getLogger(source_name).exception("Extraction failed")
            failed_sources.append(source_name)

    if failed_sources:
        logging.getLogger(__name__).error(
            "Extraction completed with failed sources: %s",
            ", ".join(failed_sources),
        )
        return 1

    logging.getLogger(__name__).info("Extraction completed successfully")
    return 0
