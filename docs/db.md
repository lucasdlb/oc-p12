# Database Operations

## Start The SQL Services

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

## Open A SQL Shell

Connect to the news database from the `news-postgres` container:

```bash
docker compose exec news-postgres psql -U news -d news
```

Connect from the host if port `5433` is available:

```bash
psql postgresql://news:news@localhost:5433/news
```

## Inspect Tables

List tables:

```sql
\dt
```

Describe the main table:

```sql
\d news_records
```

The pipeline uses `news_records_staging`, keyed by Airflow `run_id`, while loading and
merging a run. Rows for other active runs are isolated and left untouched.
Both tables are shared by every run; the pipeline does not create tables per run.
`news_records.record_id` is the primary key, so a record seen in a later run updates
the existing row instead of creating a duplicate. After a successful merge, only the
staging rows belonging to the merged run are deleted.

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

## Stop Services

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
