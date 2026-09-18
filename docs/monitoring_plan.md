# Monitoring Plan

## Objective

This plan defines how to monitor the multimodal data acquisition pipeline in local execution and in a future production deployment. It focuses on extraction reliability, data quality, multimodal coverage, database loading, and operational follow-up.

## Scope

The monitored workflow includes:

- Live extraction from NewsData.io, GDELT, and RSS feeds.
- Optional dataset extraction from Fakeddit, Climate-FEVER, and DataForGood.
- Transformation of raw JSON files into processed records.
- Validation of text, image URL format, and multimodal association.
- Airflow orchestration and PostgreSQL loading.
- KPI dashboard generation from processed data.

## Core KPIs

| KPI | Calculation | Target | Alert Threshold |
| --- | --- | --- | --- |
| Valid record percentage | Records without `validation_errors` divided by total records. | At least 90%. | Below 80%. |
| Multimodal record percentage | Records with both text and image URL divided by total records. | Track by source; live article sources should remain stable. | Drop of more than 30% compared with the previous successful run. |
| Records per source | Count grouped by `extracted_from`. | At least one live source should produce records per run. | All live source counts are zero. |
| Invalid or missing article images | Article records where `has_valid_image_url` is false. | As low as practical; RSS may vary. | More than 50% of article records. |
| Validation error count | Count grouped by each validation error code. | No sudden spikes. | Any new error code or doubling of existing error count. |
| Task execution status | Airflow task state. | All DAG tasks successful. | Any failed extract, transform, load, or merge task. |
| Load count | Rows inserted or updated in `news_records`. | Greater than zero for a successful run. | Zero loaded rows after a successful transform. |

## Monitoring Sources

| Source | Where To Check | Purpose |
| --- | --- | --- |
| Airflow UI | DAG runs and task logs for `multimodal_news_etl`. | Confirm orchestration status, task duration, and task-level failures. |
| Structured logs | `logs/` and Airflow task logs. | Diagnose source failures, retries, output paths, and record counts. |
| Structured metrics | `data/metrics/metrics.json` and `data/metrics/runs/<run_id>/metrics.json`. | Reuse extraction, transformation, and load metrics in dashboards without parsing log text. |
| Processed JSON | `data/processed/processed_records.json` and run-specific files. | Validate processed output before dashboard or database loading. |
| PostgreSQL | `news_records` table. | Confirm records were loaded and merged correctly. |
| Static KPI dashboard | `dashboard/dashboard.html`. | Present quality and coverage metrics for non-technical review. |
| Streamlit KPI dashboard | `dashboard/streamlit_app.py` at `http://localhost:8501`. | Interactive review of run metrics, processed data quality, and database load checks. |

## Verification Frequency

| Frequency | Checks |
| --- | --- |
| Every DAG run | Airflow task status, non-empty extraction output, transformation success, database load count. |
| Daily during active development | KPI dashboard, validation error counts, source counts, image URL quality. |
| Weekly | Source reliability review, API quota usage, source schema changes, sample record audit. |
| Before final delivery | Full test suite, linting, type check, sample exported data, Airflow proof of execution, dashboard export. |

## Error Handling

The live extraction policy tolerates partial source failure. NewsData.io, GDELT, and RSS are attempted independently. The live extraction step should succeed when at least one live source writes output for the run and fail when every live source fails.

If one source fails:

- Record the source name, error detail, duration, and partial output status in logs.
- Continue processing successful sources.
- Review API keys, quotas, HTTP response codes, and source availability after the run.

If every live source fails:

- Fail the Airflow task.
- Do not transform or load an empty live run.
- Check API credentials, network availability, GDELT throttling, RSS feed health, and config values.

If transformation fails:

- Inspect the raw file named in the task log.
- Check whether upstream source schemas changed.
- Add or update mapper tests before changing transformation behavior.

If database loading fails:

- Confirm the `news-postgres` service is healthy.
- Check the Airflow connection `news_postgres`.
- Inspect table schema and merge SQL in `dags/sql/`.

## Alert Priorities

| Priority | Condition | Response |
| --- | --- | --- |
| High | Full live extraction failure, transform failure, load failure, or zero loaded rows. | Investigate immediately before relying on the run. |
| Medium | Valid record rate below 80%, article image validity below 50%, or source count drops sharply. | Review source-specific logs and sample records. |
| Low | Small changes in source distribution or expected RSS image variability. | Track trend over future runs. |

## Dashboard Procedure

Generate the static dashboard after transformation:

```bash
uv run python dashboard/app.py
```

The command reads `data/processed/processed_records.json`, automatically uses the latest structured metrics file when present, and writes `dashboard/dashboard.html`. For a run-specific dashboard, pass explicit paths:

```bash
uv run python dashboard/app.py \
  --input data/processed/runs/<run_id>/processed_records.json \
  --metrics data/metrics/runs/<run_id>/metrics.json \
  --output dashboard/<run_id>.html
```

Run the interactive Streamlit dashboard locally:

```bash
uv run streamlit run dashboard/streamlit_app.py
```

Run the Streamlit dashboard with Docker Compose:

```bash
docker compose up -d dashboard
```

The Streamlit app should be used for operational review because it combines structured metrics, processed JSON quality checks, and optional PostgreSQL load checks.

## Review Checklist

- Confirm total record count is greater than zero.
- Confirm source counts match the expected active sources.
- Confirm article records preserve text and image URL in the same record.
- Review validation errors and sample records.
- Confirm Airflow task logs show successful extract, transform, load, and merge tasks.
- Confirm PostgreSQL row counts increased or merged as expected.

## Limitations

Image validation currently checks URL shape unless source-level configuration enables live URL validation. A syntactically valid image URL can still expire, redirect, block hotlinking, or return non-image content later. For production use, scheduled HTTP image validation and retention of validation timestamps should be added.
