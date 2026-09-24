import json

from news_ingestion.persistence.metrics import update_stage_metrics_file


def test_stage_metrics_track_run_record_count_and_creation_time(tmp_path):
    metrics_path = tmp_path / "metrics.json"

    update_stage_metrics_file(
        "extraction",
        {"record_count": 12},
        run_id="scheduled__2026-09-23",
        path=metrics_path,
    )
    initial_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    update_stage_metrics_file(
        "transformation",
        {"total_records": 10},
        run_id="scheduled__2026-09-23",
        path=metrics_path,
    )
    final_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert final_metrics["run_id"] == "scheduled__2026-09-23"
    assert final_metrics["records_by_run"] == {"scheduled__2026-09-23": 10}
    assert final_metrics["created_at"] == initial_metrics["created_at"]
    assert final_metrics["updated_at"] >= final_metrics["created_at"]


def test_stage_metrics_ignore_non_record_metrics(tmp_path):
    metrics_path = tmp_path / "metrics.json"

    update_stage_metrics_file(
        "custom",
        {"duration_ms": 20},
        run_id="scheduled__1",
        path=metrics_path,
    )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert "records_by_run" not in metrics
