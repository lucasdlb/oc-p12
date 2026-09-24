"""Concrete dependencies and top-level ingestion workflows."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from news_ingestion.clients.climate_fever import ClimateFeverClient
from news_ingestion.clients.dataforgood import DataForGoodClient
from news_ingestion.clients.fakeddit import FakedditClient
from news_ingestion.clients.gdelt import GdeltClient
from news_ingestion.clients.newsdata import NewsDataClient
from news_ingestion.clients.rss import RssClient
from news_ingestion.config import Settings, get_settings
from news_ingestion.paths import ProjectPaths, project_paths
from news_ingestion.persistence.json_artifacts import (
    write_raw_articles_json,
    write_raw_claims_json,
)
from news_ingestion.services.extraction import (
    AnySourceSpec,
    SourceSpec,
    extract_named_source_to_json,
    extract_sources_to_json,
)
from news_ingestion.services.results import (
    ExtractionBatchResult,
    SourceExtractionResult,
    TransformResult,
)
from news_ingestion.services.transformation import transform_raw_files_to_json


@dataclass(frozen=True)
class PipelineRunContext:
    """Resolved settings, run ID, and paths for a pipeline operation."""

    settings: Settings
    run_id: str | None
    paths: ProjectPaths

    @classmethod
    def create(
        cls,
        run_id: str | None = None,
        settings: Settings | None = None,
    ) -> PipelineRunContext:
        """Create a run context from optional settings and run ID."""
        resolved_settings = settings or get_settings()
        return cls(
            settings=resolved_settings,
            run_id=run_id,
            paths=project_paths(resolved_settings),
        )

    def live_raw_dir(self) -> Path:
        """Return the live raw directory for this run."""
        return self.paths.live_raw_dir(self.run_id)

    def processed_output_path(self) -> Path:
        """Return the live processed output path for this run."""
        return self.paths.processed_output_path(self.run_id)

    def static_raw_dir(self) -> Path:
        """Return the static raw directory."""
        return self.paths.static_raw_dir()

    def static_processed_output_path(self) -> Path:
        """Return the static processed output path."""
        return self.paths.static_processed_output_path()


LIVE_SOURCES: tuple[AnySourceSpec, ...] = (
    SourceSpec(
        name="newsdata",
        settings_key="newsdata",
        filename="newsdata_articles.json",
        fetch_records=lambda settings: NewsDataClient.from_settings(
            settings
        ).fetch_articles(),
        write_records=write_raw_articles_json,
    ),
    SourceSpec(
        name="gdelt",
        settings_key="gdelt",
        filename="gdelt_articles.json",
        fetch_records=lambda settings: GdeltClient.from_settings(
            settings
        ).fetch_articles(),
        write_records=write_raw_articles_json,
    ),
    SourceSpec(
        name="rss",
        settings_key="rss",
        filename="rss_articles.json",
        fetch_records=lambda settings: RssClient.from_settings(
            settings
        ).fetch_articles(),
        write_records=write_raw_articles_json,
    ),
)

STATIC_SOURCES: tuple[AnySourceSpec, ...] = (
    SourceSpec(
        name="fakeddit",
        settings_key="fakeddit",
        filename="fakeddit_articles.json",
        fetch_records=lambda settings: FakedditClient.from_settings(
            settings
        ).load_articles(),
        write_records=write_raw_articles_json,
    ),
    SourceSpec(
        name="climate_fever",
        settings_key="climate_fever",
        filename="climate_fever_claims.json",
        fetch_records=lambda settings: ClimateFeverClient.from_settings(
            settings
        ).fetch_claims(),
        write_records=write_raw_claims_json,
    ),
    SourceSpec(
        name="dataforgood",
        settings_key="dataforgood",
        filename="dataforgood_claims.json",
        fetch_records=lambda settings: DataForGoodClient.from_settings(
            settings
        ).fetch_claims(),
        write_records=write_raw_claims_json,
    ),
)


def extract_newsdata_to_json(
    run_id: str | None = None, settings: Settings | None = None
) -> SourceExtractionResult:
    """Extract NewsData.io articles for a live run."""
    context = PipelineRunContext.create(run_id, settings)
    return extract_named_source_to_json(
        "newsdata", LIVE_SOURCES, context.live_raw_dir(), context.settings
    )


def extract_gdelt_to_json(
    run_id: str | None = None, settings: Settings | None = None
) -> SourceExtractionResult:
    """Extract GDELT articles for a live run."""
    context = PipelineRunContext.create(run_id, settings)
    return extract_named_source_to_json(
        "gdelt", LIVE_SOURCES, context.live_raw_dir(), context.settings
    )


def extract_rss_to_json(
    run_id: str | None = None, settings: Settings | None = None
) -> SourceExtractionResult:
    """Extract RSS articles for a live run."""
    context = PipelineRunContext.create(run_id, settings)
    return extract_named_source_to_json(
        "rss", LIVE_SOURCES, context.live_raw_dir(), context.settings
    )


def extract_live_sources(
    run_id: str | None = None, settings: Settings | None = None
) -> ExtractionBatchResult:
    """Extract enabled live sources for a run."""
    context = PipelineRunContext.create(run_id, settings)
    return extract_sources_to_json(
        LIVE_SOURCES,
        context.settings,
        context.live_raw_dir(),
        "live",
        minimum_successes=1,
        minimum_records=1,
        run_id=context.run_id,
        paths=context.paths,
    )


def extract_fakeddit_to_json(
    settings: Settings | None = None,
) -> SourceExtractionResult:
    """Extract Fakeddit static article records."""
    context = PipelineRunContext.create(settings=settings)
    return extract_named_source_to_json(
        "fakeddit", STATIC_SOURCES, context.static_raw_dir(), context.settings
    )


def extract_climate_fever_to_json(
    settings: Settings | None = None,
) -> SourceExtractionResult:
    """Extract Climate-FEVER static claim records."""
    context = PipelineRunContext.create(settings=settings)
    return extract_named_source_to_json(
        "climate_fever", STATIC_SOURCES, context.static_raw_dir(), context.settings
    )


def extract_dataforgood_to_json(
    settings: Settings | None = None,
) -> SourceExtractionResult:
    """Extract DataForGood static claim records."""
    context = PipelineRunContext.create(settings=settings)
    return extract_named_source_to_json(
        "dataforgood", STATIC_SOURCES, context.static_raw_dir(), context.settings
    )


def extract_static_sources(
    settings: Settings | None = None,
) -> ExtractionBatchResult:
    """Extract all configured static sources."""
    context = PipelineRunContext.create(settings=settings)
    return extract_sources_to_json(
        STATIC_SOURCES,
        context.settings,
        context.static_raw_dir(),
        "static",
        paths=context.paths,
    )


def transform_live_run(
    input_paths: Sequence[Path],
    run_id: str | None = None,
    settings: Settings | None = None,
) -> TransformResult:
    """Transform explicit live artifacts for a run."""
    context = PipelineRunContext.create(run_id, settings)
    return transform_raw_files_to_json(
        input_paths,
        context.processed_output_path(),
        context.run_id,
        paths=context.paths,
    )


def transform_static_sources(
    input_paths: Sequence[Path], settings: Settings | None = None
) -> TransformResult:
    """Transform explicit static source artifacts."""
    context = PipelineRunContext.create(settings=settings)
    return transform_raw_files_to_json(
        input_paths,
        context.static_processed_output_path(),
        paths=context.paths,
    )
