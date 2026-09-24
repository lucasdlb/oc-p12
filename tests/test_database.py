import json

from news_ingestion.paths import ProjectPaths
from news_ingestion.services.loading import load_processed_records_to_staging


class RecordingCursor:
    def __init__(self) -> None:
        self.executed = []
        self.executed_many = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, parameters):
        self.executed.append((query, parameters))

    def executemany(self, query, rows):
        self.executed_many.append((query, rows))


class RecordingConnection:
    def __init__(self) -> None:
        self.recording_cursor = RecordingCursor()
        self.commit_count = 0

    def cursor(self):
        return self.recording_cursor

    def commit(self):
        self.commit_count += 1


def test_load_replaces_only_current_run_staging_rows(tmp_path):
    processed_path = tmp_path / "processed.json"
    processed_path.write_text(
        json.dumps(
            [
                {
                    "record_id": "article:rss:abc",
                    "record_type": "article",
                    "text": "Example",
                    "source_name": "Example",
                    "extracted_from": "rss",
                }
            ]
        ),
        encoding="utf-8",
    )
    connection = RecordingConnection()
    paths = ProjectPaths(
        raw_root=tmp_path / "raw",
        processed_root=tmp_path / "processed",
        metrics_root=tmp_path / "metrics",
    )

    loaded = load_processed_records_to_staging(
        processed_path,
        connection,
        run_id="scheduled__1",
        paths=paths,
    )

    assert loaded == 1
    assert connection.commit_count == 1
    assert connection.recording_cursor.executed == [
        (
            "DELETE FROM news_records_staging WHERE run_id = %s",
            ("scheduled__1",),
        )
    ]
    insert_query, rows = connection.recording_cursor.executed_many[0]
    assert "INSERT INTO news_records_staging" in insert_query
    assert rows[0][0] == "scheduled__1"
    assert rows[0][1] == "article:rss:abc"


def test_empty_load_clears_only_current_run_staging_rows(tmp_path):
    processed_path = tmp_path / "processed.json"
    processed_path.write_text("[]", encoding="utf-8")
    connection = RecordingConnection()
    paths = ProjectPaths(
        raw_root=tmp_path / "raw",
        processed_root=tmp_path / "processed",
        metrics_root=tmp_path / "metrics",
    )

    loaded = load_processed_records_to_staging(
        processed_path,
        connection,
        run_id="manual__1",
        paths=paths,
    )

    assert loaded == 0
    assert connection.commit_count == 1
    assert connection.recording_cursor.executed[0][1] == ("manual__1",)
    assert connection.recording_cursor.executed_many == []
