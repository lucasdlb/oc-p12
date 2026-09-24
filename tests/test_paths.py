from news_ingestion.paths import sanitize_run_id


def test_sanitize_run_id_rejects_reserved_directory_components():
    assert sanitize_run_id(".") == "manual"
    assert sanitize_run_id("..") == "manual"
    assert sanitize_run_id("scheduled__2026-09-23") == "scheduled__2026-09-23"
