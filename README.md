# Multimodal News Ingestion Pipeline

This project builds an automated data acquisition pipeline for multimodal fake-news detection research. It collects publications and claims from APIs, RSS feeds, and public datasets, keeps text and images linked in the same article records, transforms raw data into a documented schema, orchestrates live ETL with Airflow, and exposes quality KPIs through a dashboard.

## Deliverables

| Requirement | Status | Location |
| --- | --- | --- |
| Source exploration report | Complete | `docs/source_exploration.md` |
| Automated extraction script | Complete | `src/news_ingestion/cli.py` (`news-ingestion extract`) |
| Transformation pipeline | Complete | `src/news_ingestion/services/transformation.py` |
| Conceptual data schema | Complete | `docs/data_schema.md` |
| Airflow ETL DAG | Complete | `dags/multimodal_etl.py` |
| Database loading | Complete | `src/news_ingestion/services/loading.py`, `src/news_ingestion/persistence/postgres.py`, `src/news_ingestion/sql/`, `docs/db.md` |
| KPI dashboard / monitoring interface | Complete | `dashboard/streamlit_app.py` |
| Monitoring plan | Complete | `docs/monitoring_plan.md` |
| Airflow execution evidence | To provide | Airflow UI screenshots or exported run logs |

## Project Structure

```text
.
├── dashboard/              # Interactive Streamlit KPI dashboard
├── dags/                   # Airflow workflow definition
├── data/                   # Raw and processed JSON outputs
├── docs/                   # Project reports and operational documentation
├── src/news_ingestion/     # Clients, services, persistence, CLI, and packaged SQL
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
uv sync --all-groups --all-extras
```

Create the local environment file from the example:

```bash
cp .env.example .env
```

Set `NEWS_DATA_API_KEY` before running NewsData.io extraction. Hugging Face sources can optionally use `HF_TOKEN` depending on dataset access requirements.

## Run Extraction

The official executable extraction script is the `news-ingestion` CLI entry point,
implemented in `src/news_ingestion/cli.py`. The Airflow DAG reuses the same
application services; it is the orchestrator, not a separate extraction implementation.

Fetch all enabled live sources:

```bash
uv run news-ingestion extract --group live
```

Or run individual extractors:

```bash
uv run news-ingestion extract --source newsdata
uv run news-ingestion extract --source gdelt
uv run news-ingestion extract --source rss
uv run news-ingestion extract --source fakeddit
uv run news-ingestion extract --source climate-fever
uv run news-ingestion extract --source dataforgood
uv run news-ingestion extract --group static
```

Configuration is read from `config.toml`.

Live outputs are written to `data/raw/live/` for manual runs or `data/raw/live/runs/<run_id>/` for Airflow runs. Static source outputs are written to `data/raw/static/`.

## Transform Data

```bash
uv run news-ingestion transform --group live
uv run news-ingestion transform --group static
```

The default processed output is `data/processed/processed_records.json`. Airflow runs write to `data/processed/runs/<run_id>/processed_records.json`, and static transforms write to `data/processed/static/processed_records.json`. The conceptual schema and validation rules are documented in `docs/data_schema.md`.

## Airflow ETL

Start Airflow and PostgreSQL services:

```bash
docker compose up -d
```

Open Airflow at `http://localhost:8080` and run the `multimodal_news_etl` DAG. The DAG extracts live sources, transforms the run output, loads processed records into run-scoped staging, and merges them into `news_records`.

Database inspection commands are documented in `docs/db.md`.

## KPI Dashboard

Run the Streamlit dashboard locally:

```bash
uv run streamlit run dashboard/streamlit_app.py
```

The app opens at `http://localhost:8501`. Dataset metrics and samples come from
PostgreSQL when `NEWS_DASHBOARD_DATABASE_URL` is configured. The Pipeline Runs tab
provides a run selector plus aggregate and per-run views from structured metrics in
`data/metrics/runs`.

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
