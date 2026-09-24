import json
import os
import runpy
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

dashboard = runpy.run_path(
    str(Path(__file__).parents[1] / "dashboard" / "streamlit_app.py")
)
aggregate_pipeline_metrics = dashboard["aggregate_pipeline_metrics"]
load_pipeline_runs = dashboard["load_pipeline_runs"]
pipeline_run_rows = dashboard["pipeline_run_rows"]
query_database_metrics = dashboard["query_database_metrics"]
query_database_samples = dashboard["query_database_samples"]


class FakePsycopgError(Exception):
    pass


class FakeCursor:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.current = None
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters=()):
        self.executions.append((query, parameters))
        self.current = next(self.responses)

    def fetchone(self):
        return self.current

    def fetchall(self):
        return self.current


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.fake_cursor


def install_fake_psycopg(monkeypatch, cursor):
    module = ModuleType("psycopg")
    module.__dict__.update(
        Error=FakePsycopgError,
        connect=lambda _database_url: FakeConnection(cursor),
    )
    monkeypatch.setitem(sys.modules, "psycopg", module)


def test_load_pipeline_runs_returns_valid_files_newest_first(tmp_path):
    older = tmp_path / "runs" / "older" / "metrics.json"
    newer = tmp_path / "runs" / "newer" / "metrics.json"
    invalid = tmp_path / "runs" / "invalid" / "metrics.json"
    older.parent.mkdir(parents=True)
    newer.parent.mkdir(parents=True)
    invalid.parent.mkdir(parents=True)
    older.write_text(json.dumps({"run_id": "older"}), encoding="utf-8")
    newer.write_text(json.dumps({"run_id": "newer"}), encoding="utf-8")
    invalid.write_text("not json", encoding="utf-8")
    older.touch()
    newer.touch()
    older_mtime = older.stat().st_mtime - 10
    os.utime(older, (older_mtime, older_mtime))

    runs = load_pipeline_runs(tmp_path)

    assert [metrics["run_id"] for _, metrics in runs] == ["newer", "older"]


def test_aggregate_pipeline_metrics_handles_partial_runs():
    complete = {
        "run_id": "scheduled__1",
        "extraction": {
            "record_count": 12,
            "sources_failed": 1,
            "sources": [{"duration_ms": 10}, {"duration_ms": 20}],
        },
        "transformation": {"total_records": 12, "duration_ms": 4},
        "load": {"loaded_records": 12, "duration_ms": 2},
    }
    partial = {
        "run_id": "scheduled__2",
        "extraction": {
            "record_count": 8,
            "sources_failed": 0,
            "duration_ms": 6,
        },
        "transformation": {"total_records": 8, "duration_ms": 2},
    }

    aggregate = aggregate_pipeline_metrics([complete, partial])
    rows = pipeline_run_rows([complete, partial])

    assert aggregate == {
        "total_runs": 2,
        "complete_runs": 1,
        "extracted_records": 20,
        "processed_records": 20,
        "loaded_records": 12,
        "source_failures": 1,
        "average_extraction_duration_ms": 18.0,
        "average_transformation_duration_ms": 3.0,
        "average_load_duration_ms": 2.0,
    }
    assert [row["status"] for row in rows] == ["complete", "incomplete"]


def test_query_database_metrics_maps_database_aggregates(monkeypatch):
    loaded_at = datetime(2026, 9, 24, tzinfo=UTC)
    cursor = FakeCursor(
        [
            (10, 8, 7, 6, 5, loaded_at),
            [("rss", 6), ("gdelt", 4)],
            [("article", 6), ("claim", 4)],
            [("missing_text", 2)],
        ]
    )
    install_fake_psycopg(monkeypatch, cursor)

    metrics = query_database_metrics("postgresql://example")

    assert metrics["total_records"] == 10
    assert metrics["valid_record_rate"] == 80.0
    assert metrics["multimodal_rate"] == 70.0
    assert metrics["valid_article_image_rate"] == 83.3
    assert metrics["records_by_source"] == {"rss": 6, "gdelt": 4}
    assert metrics["records_by_type"] == {"article": 6, "claim": 4}
    assert metrics["validation_errors"] == {"missing_text": 2}
    assert metrics["latest_loaded_at"] == "2026-09-24T00:00:00+00:00"


def test_query_database_samples_applies_source_filter(monkeypatch):
    loaded_at = datetime(2026, 9, 24, tzinfo=UTC)
    cursor = FakeCursor([[("article", "rss", "BBC", True, [], "News text", loaded_at)]])
    install_fake_psycopg(monkeypatch, cursor)

    records = query_database_samples("postgresql://example", "rss")

    assert records == [
        {
            "record_type": "article",
            "extracted_from": "rss",
            "source_name": "BBC",
            "is_multimodal": True,
            "validation_errors": [],
            "text": "News text",
            "loaded_at": loaded_at,
        }
    ]
    assert cursor.executions[0][1] == ("rss",)
