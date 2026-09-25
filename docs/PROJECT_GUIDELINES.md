# Multimodal Data Extraction for Fake News Detection

## Project Purpose

CheckIt.AI develops artificial intelligence tools to help detect misinformation automatically. The goal of this project is to build an automated data acquisition pipeline that collects multimodal publications, meaning records that contain both text and images, from one or more accessible sources such as APIs, news websites, social platforms, datasets, or RSS feeds.

The extracted data will be used to enrich a future fake news detection engine. The project goes beyond a simple extraction script: it must cover source qualification, automated extraction, transformation, orchestration, monitoring, and evaluation.

## Mission Objective

Create an automated extraction system able to retrieve publications such as articles or posts, including both textual content and associated images. The output must be structured, reproducible, and suitable for downstream data analysis or machine learning workflows.

## Main Requirements

- Collect both text and image data.
- Keep each text and its related image associated in the same record.
- Use one or more accessible sources: API, website, RSS feed, public dataset, or similar.
- Store the extracted data in a coherent structure such as JSON or CSV.
- Build scripts that are modular, executable, and understandable.
- Document technical decisions, selected sources, schema, and monitoring strategy.

## Step 1: Explore and Qualify Data Sources

Identify at least three relevant multimodal sources that could be used to train or support a fake news detection system.

For each source, document:

- Source name and access method.
- Data type: text, image, metadata, labels, or mixed content.
- Format: CSV, JSON, API response, HTML page, PDF, or other.
- Language.
- Label quality, when available, especially true or false labels.
- Extraction method: REST API, scraping, Selenium, Scrapy, download, or RSS.
- Usage rights and reliability.
- Expected output format.

Expected deliverable:

- Source exploration report in Markdown or PDF.

Recommendations:

- Explore sources such as News API, Reddit, Kaggle, Hugging Face Datasets, Google Dataset Search, public-apis.io, and news websites.
- Identify indispensable fields for each publication, such as title, text, image URL, publication date, source URL, domain, and reliability indicator.
- Prefer official APIs and public datasets before scraping websites.
- Do not ignore RSS feeds.
- Check usage rights and source reliability.
- Define the target output format early, such as JSON, CSV, or Parquet.

Vigilance points:

- Do not confuse controversial opinions with misinformation.
- Controversial opinions are subjective viewpoints or judgments that may shock, offend, or contradict social or scientific norms, but still belong to freedom of expression.
- Misinformation or disinformation refers to false information spread to deceive, manipulate, create doubt, or cause harm.
- Do not ignore useful secondary fields such as URL, declared reliability, source name, or domain name.
- Verify that image and text fields are correctly linked in the same entry.

## Step 2: Develop Automated Extraction Scripts

Create Python scripts to extract multimodal data from one or more selected sources. The scripts must be modular, executable without manual intervention, and able to save data in a coherent structure.

Expected deliverable:

- Automated extraction scripts as `.py` or `.ipynb` files.

Recommendations:

- Check that image links are usable, accessible, and available in a valid format.
- Test JSON or HTML responses before building the full extraction logic.
- Structure the code into clear functions for connection, parsing, cleaning, and saving.
- Add logging, error handling with `try` and `except`, and configurable parameters.
- Keep the code understandable enough to explain the full technical path and decisions.

Vigilance points:

- Respect API call limits, quotas, and access keys.
- Make sure scraping is legal and allowed for any targeted website.
- Avoid relying on fragile selectors when a stable API or feed exists.

Possible tools:

- Python
- Requests
- Beautiful Soup
- Selenium
- Scrapy
- Feedparser

## Step 3: Implement a Transformation Pipeline

Develop a modular Python pipeline to transform extracted raw data into an exploitable format. This includes cleaning, normalization, mapping, validation, and column generation.

The pipeline must be reproducible and logged. The transformed data must be documented through a conceptual schema.

Expected deliverables:

- Reproducible transformation pipeline as a `.py` or `.ipynb` file.
- Final data schema as PDF, Mermaid, or equivalent diagram.

Recommendations:

- Structure the pipeline into clear stages: read, transform, validate, export.
- Modularize functions such as `clean_text()` and `validate_image()`.
- Use logging to record every major transformation.
- Use Mermaid or draw.io to visualize columns and relationships.
- Define fields such as title, content, image URL, metadata, label, source, and extraction date.
- Explain the role of each field for the use case, such as classification, NLP, image processing, traceability, or monitoring.

Vigilance points:

- Do not confuse a physical or technical database schema with a conceptual data model.
- A technical schema describes how data is physically stored in a system, including tables, columns, data types, indexes, keys, and platform-specific constraints.
- A conceptual model explains the business meaning of the data independently of storage implementation. It focuses on entities, relationships, attributes, and integrity constraints.
- Do not confuse source exploration with data transformation.
- Verify that text-image associations remain valid after transformation.

Possible tools:

- Python
- Mermaid
- draw.io
- Logging

## Step 4: Orchestrate the Pipeline with Airflow

Create an ETL workflow with Apache Airflow to automate extraction, transformation, and loading of multimodal data into a suitable storage system such as SQL or NoSQL.

The DAG must include distinct tasks for each step and be executable locally.

Expected deliverable:

- Airflow ETL flow demonstration as a `.py` DAG, with proof of execution such as logs or Airflow UI screenshots.

Recommendations:

- Reuse functions from the extraction and transformation scripts inside the DAG.
- Keep Airflow tasks short, explicit, and modular.
- Use simple `PythonOperator` tasks where possible.
- Choose a database type that matches the data and project needs.

Vigilance points:

- Import all required Airflow operators correctly.
- Avoid tasks that are too long or not modular enough.
- Secure the database if one is used.
- Add authentication where needed.
- Limit access to authorized roles.
- Encrypt sensitive data where relevant.

Possible tools:

- Python
- Apache Airflow

## Step 5: Evaluate and Visualize Performance

Define performance indicators to evaluate the effectiveness of the pipeline, including data quality, speed, and cost.

Create a dashboard to visualize these KPIs and a monitoring plan to follow the pipeline in production.

Expected deliverables:

- ETL KPI dashboard as a `.py` or `.ipynb` file.
- Monitoring plan in Markdown or PDF.

Recommended KPIs:

- Percentage of valid records.
- Percentage of records with both text and image.
- Number of extracted records per source.
- Execution time per task.
- Error rate per source or pipeline stage.
- API usage or resource cost.
- Number of inaccessible images.

Recommendations:

- Measure data accuracy, execution speed, and resource usage.
- Use a dashboard readable by a non-technical audience.
- Include alert thresholds, error management, and verification frequency in the monitoring plan.
- Ensure the monitoring plan is aligned with the implemented automations.

Possible tool:

- Streamlit

## Suggested Resources

- Google Dataset Search
- Hugging Face Datasets
- Kaggle
- public-apis.io
- NewsData.io API
- Multimodal Fake News Detection: A Survey
- Airflow Python package documentation
- Apache Airflow Docker quickstart
- Airflow `PythonOperator` tutorials
- Building an ETL pipeline with Airflow
- Streamlit documentation

## Suggested Repository Structure

```text
.
├── data/
│   ├── raw/
│   └── processed/
├── dags/
│   └── multimodal_etl.py
├── docs/
│   ├── source_exploration.md
│   ├── data_schema.md
│   └── monitoring_plan.md
├── notebooks/
├── src/
│   ├── extraction/
│   ├── transformation/
│   └── validation/
├── dashboard/
│   └── app.py
├── tests/
├── PROJECT_GUIDELINES.md
└── README.md
```

## Final Deliverables Checklist

- Source exploration report.
- Automated extraction scripts.
- Reproducible transformation pipeline.
- Final conceptual data schema.
- Airflow DAG demonstrating the ETL flow.
- KPI dashboard.
- Monitoring plan.
- Evidence of execution, such as logs, screenshots, or exported files.
