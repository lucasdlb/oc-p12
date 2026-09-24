CREATE TABLE IF NOT EXISTS news_records_staging (
    run_id TEXT NOT NULL,
    LIKE news_records INCLUDING DEFAULTS
);

CREATE UNIQUE INDEX IF NOT EXISTS news_records_staging_run_record_idx
    ON news_records_staging (run_id, record_id);
