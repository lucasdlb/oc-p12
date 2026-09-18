# Multimodal News Ingestion Pipeline

This project builds an automated data acquisition pipeline for multimodal fake-news detection research. It collects publications and claims from APIs, RSS feeds, and public datasets, keeps text and images linked in the same article records, transforms raw data into a documented schema, orchestrates live ETL with Airflow, and exposes quality KPIs through a dashboard.

## Deliverables

| Requirement | Status | Location |
| --- | --- | --- |
| Source exploration report | Complete | `docs/source_exploration.md` |
| Automated extraction scripts | Complete | `scripts/`, `src/news_ingestion/*_client.py` |
| Transformation pipeline | Complete | `scripts/transform_raw_data.py`, `src/news_ingestion/transformation.py` |
| Conceptual data schema | Complete | `docs/data_schema.md` |
| Airflow ETL DAG | Complete | `dags/multimodal_etl.py` |
| Database loading | Complete | `src/news_ingestion/database.py`, `dags/sql/`, `docs/db.md` |
| KPI dashboard | Complete | `dashboard/app.py`, `dashboard/streamlit_app.py` |
| Monitoring plan | Complete | `docs/monitoring_plan.md` |

## Project Structure

```text
.
├── dashboard/              # KPI dashboard generator and generated HTML output
├── dags/                   # Airflow DAG and SQL files
├── data/                   # Raw and processed JSON outputs
├── docs/                   # Project reports and operational documentation
├── scripts/                # Command-line extraction and transformation scripts
├── src/news_ingestion/     # Pipeline package
└── tests/                  # Unit tests
```

## Data Sources

Primary multimodal sources:

- Fakeddit: labelled multimodal Reddit dataset.
- NewsData.io: live news API with article text and image URLs when available.
- GDELT 2.1 DOC API: public article discovery API with title and social image metadata.
- RSS feeds: public news and fact-checking feeds with text and optional media metadata.

Complementary labelled text sources:

- Climate-FEVER: climate claim verification dataset.
- DataForGood climate misinformation RCoT: climate misinformation transcript dataset.

See `docs/source_exploration.md` for qualification details, risks, usage rights, and output schemas.

## Setup

The project uses Python 3.12 and `uv`.

```bash
uv sync --all-groups
```

Create local environment files from the examples when needed:

```bash
cp .env.example .env
cp .env.airflow.exemple .env.airflow
```

Set `NEWS_DATA_API_KEY` before running NewsData.io extraction. Hugging Face sources can optionally use `HF_TOKEN` depending on dataset access requirements.

## Run Extraction

Fetch all configured non-live sources:

```bash
uv run python scripts/fetch_all_sources.py
```

Or run individual extractors:

```bash
uv run python scripts/fetch_newsdata.py
uv run python scripts/fetch_gdelt.py
uv run python scripts/fetch_rss.py
uv run python scripts/fetch_fakeddit.py
uv run python scripts/fetch_climate_fever.py
uv run python scripts/fetch_dataforgood.py
```

Configuration is read from `config.toml`.

## Transform Data

```bash
uv run python scripts/transform_raw_data.py
```

The default processed output is `data/processed/processed_records.json`. The conceptual schema and validation rules are documented in `docs/data_schema.md`.

## Airflow ETL

Start Airflow and PostgreSQL services:

```bash
docker compose up -d
```

Open Airflow at `http://localhost:8080` and run the `multimodal_news_etl` DAG. The DAG extracts live sources, transforms the run output, loads processed records into a temporary table, and merges them into `news_records`.

Database inspection commands are documented in `docs/db.md`.

## KPI Dashboard

Generate the static HTML dashboard from the default processed dataset:

```bash
uv run python dashboard/app.py
```

The generated report is written to `dashboard/dashboard.html`. It includes valid record percentage, multimodal coverage, valid article image percentage, invalid or missing image count, records per source, validation errors, and sample records.

Pipeline stages also write structured metrics to `data/metrics/metrics.json` for manual runs or `data/metrics/runs/<run_id>/metrics.json` for Airflow runs. The dashboard automatically reads the latest metrics file when available, so the same extraction, transformation, and load metrics that appear in logs are reused in the dashboard.

To generate a dashboard for a specific Airflow run:

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

The app opens at `http://localhost:8501`. It reads structured metrics, processed JSON, and can query PostgreSQL when `NEWS_DASHBOARD_DATABASE_URL` is configured.

Run the independent Streamlit dashboard service with Docker Compose:

```bash
docker compose up -d dashboard
```

The Compose service uses `postgresql://news:news@news-postgres:5432/news` inside the Docker network and exposes the UI on `http://localhost:8501`.
It builds from `Dockerfile.dashboard` and does not reuse the Airflow entrypoint.

## Monitoring

The monitoring plan is in `docs/monitoring_plan.md`. It defines KPIs, alert thresholds, verification frequency, source failure handling, and review procedures.

## Quality Checks

Run tests:

```bash
uv run pytest
```

Run linting and formatting checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

Run type checking:

```bash
uv run ty check
```

Pre-commit hooks are configured in `.pre-commit-config.yaml`.
