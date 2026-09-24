from importlib.resources import files


def migration_sql(file_name: str) -> str:
    return (
        files("news_ingestion.sql.migrations")
        .joinpath(file_name)
        .read_text(encoding="utf-8")
    )


def test_main_table_deduplicates_records_across_runs():
    create_sql = migration_sql("create_news_records.sql")
    merge_sql = migration_sql("merge_records.sql")

    assert "record_id TEXT PRIMARY KEY" in create_sql
    assert "ON CONFLICT (record_id) DO UPDATE" in merge_sql


def test_staging_is_shared_and_isolated_by_run():
    staging_sql = migration_sql("create_news_records_staging.sql")
    merge_sql = migration_sql("merge_records.sql")

    assert "(run_id, record_id)" in staging_sql
    assert "WHERE run_id = %(run_id)s" in merge_sql
    assert "DELETE FROM news_records_staging" in merge_sql
