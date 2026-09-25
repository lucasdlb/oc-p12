# Multimodal News Ingestion Pipeline

This project builds an automated data acquisition pipeline for multimodal fake-news detection research. It collects publications and claims from APIs, RSS feeds, and public datasets, keeps text and images linked in the same article records, transforms raw data into a documented schema, orchestrates live ETL with Airflow, and exposes quality KPIs through a dashboard.

Repository: https://github.com/lucasdlb/oc-p12

## Deliverables

| Livrable | Fichiers à consulter |
| --- | --- |
| Rapport d'exploration de données | `docs/source_exploration.md` |
| Scripts d'extraction automatisée | `src/news_ingestion/cli.py`, `src/news_ingestion/services/extraction.py`, `src/news_ingestion/clients/` |
| Pipeline de transformation reproductible | `src/news_ingestion/services/transformation.py`, commande `news-ingestion transform` |
| Schéma de données finalisé | `docs/data_schema.md` |
| Flux ETL Airflow | `dags/multimodal_etl.py` |
| Tableau de bord KPI de l'ETL | `dashboard/streamlit_app.py` |
| Plan de monitoring | `docs/monitoring_plan.md` |
| Preuves d'exécution Airflow | Captures d'écran Airflow à ajouter au rendu final |

## Project Structure

```text
.
├── dashboard/              # Interactive Streamlit KPI dashboard
├── dags/                   # Airflow workflow definition
├── data/                   # Raw and processed JSON outputs
├── docs/                   # Project reports and operational documentation
├── external/               # Optional external datasets, not versioned
├── src/news_ingestion/     # Clients, services, persistence, CLI, and packaged SQL
└── tests/                  # Unit tests
```

## Data Sources

Primary multimodal sources:

- Fakeddit: labelled multimodal Reddit dataset, optional and disabled by default because the TSV files are external data.
- NewsData.io: live news API with article text and image URLs when available.
- GDELT 2.1 DOC API: public article discovery API with title and social image metadata.
- RSS feeds: public news and fact-checking feeds with text and optional media metadata.

Complementary labelled text sources:

- Climate-FEVER: climate claim verification dataset.
- DataForGood climate misinformation RCoT: climate misinformation transcript dataset.

See `docs/source_exploration.md` for qualification details, risks, usage rights, and output schemas.

### Optional Fakeddit Dataset

Fakeddit is supported by the pipeline, but its TSV files are not versioned in this repository. To enable it, download the Fakeddit multimodal TSV files and place them here:

```text
external/Fakeddit/
├── multimodal_train.tsv
├── multimodal_validate.tsv
└── multimodal_test.tsv
```

Then set `enabled = true` in the `[fakeddit]` section of `config.toml` and run:

```bash
uv run news-ingestion extract --source fakeddit
```

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

### Airflow Execution Evidence

![Airflow UI](docs/Airflow-ui.png)

## Database Operations

Start only the application PostgreSQL service:

```bash
docker compose up -d news-postgres
```

Start Airflow and all database services:

```bash
docker compose up -d
```

Check container status:

```bash
docker compose ps
```

Connect to the news database from the `news-postgres` container:

```bash
docker compose exec news-postgres psql -U news -d news
```

Connect from the host if port `5433` is available:

```bash
psql postgresql://news:news@localhost:5433/news
```

List tables:

```sql
\dt
```

Describe the main table:

```sql
\d news_records
```

The pipeline uses `news_records_staging`, keyed by Airflow `run_id`, while loading and merging a run. Rows for other active runs are isolated and left untouched. Both tables are shared by every run; the pipeline does not create tables per run. `news_records.record_id` is the primary key, so a record seen in a later run updates the existing row instead of creating a duplicate. After a successful merge, only the staging rows belonging to the merged run are deleted.

Count loaded records:

```sql
SELECT COUNT(*) FROM news_records;
```

Count records by extraction source:

```sql
SELECT extracted_from, COUNT(*)
FROM news_records
GROUP BY extracted_from
ORDER BY COUNT(*) DESC;
```

Inspect multimodal coverage:

```sql
SELECT record_type, is_multimodal, COUNT(*)
FROM news_records
GROUP BY record_type, is_multimodal
ORDER BY record_type, is_multimodal;
```

Inspect recent rows:

```sql
SELECT record_id, record_type, extracted_from, source_name, is_multimodal, loaded_at
FROM news_records
ORDER BY loaded_at DESC
LIMIT 5;
```

Inspect validation errors:

```sql
SELECT validation_errors, COUNT(*)
FROM news_records
GROUP BY validation_errors
ORDER BY COUNT(*) DESC;
```

Stop containers while keeping volumes:

```bash
docker compose stop
```

Remove containers while keeping named volumes:

```bash
docker compose down
```

Remove containers and database volumes:

```bash
docker compose down -v
```

Use `docker compose down -v` only when the local database can be deleted.

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

### Dashboard Screenshots

![Database metrics](docs/Streamlit-dashboard-db-metrics.png)

![Pipeline metrics](docs/Streamlit-dashboard-pipeline-metrics.png)

![All pipeline metrics](docs/Streamlit-dashboard-all-pipeline-metrics.png)

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
