import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from news_ingestion.composition import transform_live_run
from news_ingestion.config import Settings
from news_ingestion.models import RawArticle
from news_ingestion.paths import ProjectPaths
from news_ingestion.persistence.json_artifacts import write_raw_articles_json
from news_ingestion.services.extraction import (
    SourceSpec,
    extract_sources_to_json,
)
from news_ingestion.services.results import TransformResult


def article_source(fetch_records):
    return SourceSpec[RawArticle](
        name="source",
        settings_key="source",
        filename="source_articles.json",
        fetch_records=fetch_records,
        write_records=write_raw_articles_json,
    )


def test_extract_sources_raises_when_no_sources_enabled(tmp_path):
    source = article_source(lambda settings: [])
    settings = cast(
        Settings,
        SimpleNamespace(source=SimpleNamespace(enabled=False)),
    )

    with pytest.raises(RuntimeError, match="No enabled live sources"):
        extract_sources_to_json((source,), settings, tmp_path, "live")


def test_extract_sources_returns_artifact_metadata(tmp_path):
    article = RawArticle(
        article_id="article-1",
        title="Title",
        link=None,
        description=None,
        content=None,
        image_url="https://example.com/image.jpg",
        published_at=None,
        source_id=None,
        source_name=None,
        language=None,
        country=[],
        category=[],
        extracted_from="source",
        raw_payload={},
    )
    source = article_source(lambda settings: [article])
    settings = cast(
        Settings,
        SimpleNamespace(source=SimpleNamespace(enabled=True)),
    )
    metrics_path = tmp_path / "metrics.json"

    result = extract_sources_to_json(
        (source,),
        settings,
        tmp_path / "raw",
        "live",
        minimum_records=1,
        paths=None,
    )

    assert result.record_count == 1
    assert result.artifact_paths == (tmp_path / "raw" / "source_articles.json",)
    assert (
        json.loads(result.artifact_paths[0].read_text(encoding="utf-8"))[0][
            "article_id"
        ]
        == "article-1"
    )
    assert not metrics_path.exists()


def test_extract_sources_rejects_empty_batch(tmp_path):
    source = article_source(lambda settings: [])
    settings = cast(
        Settings,
        SimpleNamespace(source=SimpleNamespace(enabled=True)),
    )

    with pytest.raises(RuntimeError, match="at least 1 required"):
        extract_sources_to_json(
            (source,),
            settings,
            tmp_path / "raw",
            "live",
            minimum_records=1,
        )


def test_transform_live_run_passes_explicit_artifacts(tmp_path, monkeypatch):
    settings = cast(
        Settings,
        SimpleNamespace(
            project_root=tmp_path,
            raw_data_dir=tmp_path / "raw",
            processed_data_dir=tmp_path / "processed",
            metrics_data_dir=tmp_path / "metrics",
        ),
    )
    input_paths = [tmp_path / "raw" / "source_articles.json"]
    calls = []

    def fake_transform_raw_files_to_json(
        artifacts: list[Path],
        output_path: Path,
        run_id: str | None = None,
        *,
        paths=None,
    ) -> TransformResult:
        calls.append(
            {
                "artifacts": artifacts,
                "output_path": output_path,
                "run_id": run_id,
                "paths": paths,
            }
        )
        return TransformResult(output_path, 1, 10)

    monkeypatch.setattr(
        "news_ingestion.composition.transform_raw_files_to_json",
        fake_transform_raw_files_to_json,
    )

    result = transform_live_run(input_paths, "dag run/1", settings)
    output_path = (
        tmp_path / "processed" / "runs" / "dag_run_1" / "processed_records.json"
    )

    assert result.artifact_path == output_path
    assert calls == [
        {
            "artifacts": input_paths,
            "output_path": output_path,
            "run_id": "dag run/1",
            "paths": ProjectPaths(
                raw_root=tmp_path / "raw",
                processed_root=tmp_path / "processed",
                metrics_root=tmp_path / "metrics",
            ),
        }
    ]
