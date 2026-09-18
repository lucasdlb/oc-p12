from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from news_ingestion.metrics import latest_metrics_path, load_metrics

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "processed_records.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "dashboard" / "dashboard.html"


def load_records(input_path: Path) -> list[dict[str, Any]]:
    records = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        msg = f"Expected {input_path} to contain a JSON array."
        raise TypeError(msg)
    invalid_records = [record for record in records if not isinstance(record, dict)]
    if invalid_records:
        msg = f"Expected every record in {input_path} to be a JSON object."
        raise TypeError(msg)
    return records


def build_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_records = len(records)
    valid_records = sum(1 for record in records if not record.get("validation_errors"))
    multimodal_records = sum(1 for record in records if record.get("is_multimodal"))
    valid_image_records = sum(
        1 for record in records if record.get("has_valid_image_url")
    )
    article_records = sum(
        1 for record in records if record.get("record_type") == "article"
    )
    invalid_or_missing_images = sum(
        1
        for record in records
        if record.get("record_type") == "article"
        and not record.get("has_valid_image_url")
    )
    word_counts = [int(record.get("word_count") or 0) for record in records]
    text_lengths = [int(record.get("text_length") or 0) for record in records]

    return {
        "total_records": total_records,
        "valid_records": valid_records,
        "valid_record_rate": percentage(valid_records, total_records),
        "multimodal_records": multimodal_records,
        "multimodal_rate": percentage(multimodal_records, total_records),
        "valid_image_records": valid_image_records,
        "valid_image_rate": percentage(valid_image_records, article_records),
        "invalid_or_missing_images": invalid_or_missing_images,
        "avg_word_count": round(mean(word_counts), 1) if word_counts else 0,
        "avg_text_length": round(mean(text_lengths), 1) if text_lengths else 0,
        "source_counts": Counter(
            str(record.get("extracted_from") or "unknown") for record in records
        ),
        "record_type_counts": Counter(
            str(record.get("record_type") or "unknown") for record in records
        ),
        "validation_error_counts": validation_error_counts(records),
    }


def percentage(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def validation_error_counts(records: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for record in records:
        errors = record.get("validation_errors")
        if isinstance(errors, list):
            counts.update(str(error) for error in errors)
    return counts


def render_dashboard(
    records: list[dict[str, Any]], metrics: dict[str, Any], run_metrics: dict[str, Any]
) -> str:
    source_counts = metrics["source_counts"]
    validation_error_counts = metrics["validation_error_counts"]
    pipeline_metrics = render_pipeline_metrics(run_metrics)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Multimodal News ETL KPI Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f0ea;
      --card: #fffaf2;
      --ink: #23201d;
      --muted: #6b6258;
      --accent: #245f73;
      --accent-soft: #d6e7eb;
      --warning: #9b3d1f;
      --line: #ded3c4;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Georgia, "Times New Roman", serif;
      line-height: 1.45;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 48px; }}
    header {{ margin-bottom: 28px; }}
    h1 {{ font-size: clamp(2rem, 4vw, 4rem); line-height: 0.95; margin: 0 0 12px; }}
    h2 {{ margin-top: 36px; border-top: 1px solid var(--line); padding-top: 22px; }}
    .subtitle {{ color: var(--muted); max-width: 780px; font-size: 1.08rem; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }}
    .card {{ background: var(--card); border: 1px solid var(--line); padding: 18px; border-radius: 18px; box-shadow: 0 12px 28px rgb(48 38 26 / 8%); }}
    .label {{ color: var(--muted); font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    .value {{ font-size: 2rem; margin-top: 8px; font-weight: 700; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; }}
    .bar-row {{ display: grid; grid-template-columns: 150px 1fr 70px; gap: 12px; align-items: center; margin: 10px 0; }}
    .bar-label {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .bar-track {{ background: #eadfce; border-radius: 999px; height: 14px; overflow: hidden; }}
    .bar {{ height: 100%; background: var(--accent); border-radius: 999px; }}
    .warning .bar {{ background: var(--warning); }}
    table {{ width: 100%; border-collapse: collapse; background: var(--card); border-radius: 18px; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 12px; text-align: left; vertical-align: top; }}
    th {{ background: var(--accent-soft); font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.07em; }}
    td {{ font-size: 0.92rem; }}
    .empty {{ color: var(--muted); background: var(--card); border: 1px solid var(--line); border-radius: 18px; padding: 18px; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Multimodal News ETL KPI Dashboard</h1>
      <p class="subtitle">This dashboard summarizes processed pipeline output for data quality, multimodal coverage, source balance, and validation issues.</p>
    </header>
    <section class="cards">
      {metric_card("Total records", metrics["total_records"])}
      {metric_card("Valid records", f"{metrics['valid_record_rate']}%")}
      {metric_card("Multimodal records", f"{metrics['multimodal_rate']}%")}
      {metric_card("Valid article images", f"{metrics['valid_image_rate']}%")}
      {metric_card("Invalid/missing images", metrics["invalid_or_missing_images"])}
      {metric_card("Average words", metrics["avg_word_count"])}
    </section>
    <section class="grid">
      {pipeline_metrics}
      <div>
        <h2>Records Per Source</h2>
        {render_bars(source_counts)}
      </div>
      <div>
        <h2>Validation Errors</h2>
        {render_bars(validation_error_counts, warning=True) if validation_error_counts else '<div class="empty">No validation errors found.</div>'}
      </div>
    </section>
    <section>
      <h2>Recent Sample Records</h2>
      {render_sample_table(records)}
    </section>
  </main>
</body>
</html>
"""


def metric_card(label: str, value: object) -> str:
    return f"""<article class="card">
  <div class="label">{escape(label)}</div>
  <div class="value">{escape(value)}</div>
</article>"""


def render_bars(counts: Counter[str], warning: bool = False) -> str:
    max_count = max(counts.values(), default=1)
    css_class = " warning" if warning else ""
    rows = []
    for label, count in counts.most_common():
        width = round((count / max_count) * 100, 1)
        rows.append(
            f"""<div class="bar-row{css_class}">
  <div class="bar-label" title="{escape(label)}">{escape(label)}</div>
  <div class="bar-track"><div class="bar" style="width: {width}%"></div></div>
  <div>{count}</div>
</div>"""
        )
    return "\n".join(rows)


def render_pipeline_metrics(run_metrics: dict[str, Any]) -> str:
    if not run_metrics:
        return """<div>
  <h2>Pipeline Run Metrics</h2>
  <div class="empty">No structured run metrics found. Generate them by running extraction, transformation, or Airflow.</div>
</div>"""

    extraction = as_dict(run_metrics.get("extraction"))
    transformation = as_dict(run_metrics.get("transformation"))
    load = as_dict(run_metrics.get("load"))
    rows = [
        ("Run ID", run_metrics.get("run_id") or "static/manual"),
        ("Updated at", run_metrics.get("updated_at") or ""),
        ("Sources succeeded", extraction.get("sources_succeeded", "")),
        ("Sources failed", extraction.get("sources_failed", "")),
        ("Extracted records", extraction.get("record_count", "")),
        ("Transformed records", transformation.get("total_records", "")),
        ("Loaded records", load.get("loaded_records", "")),
    ]
    items = "".join(
        f"<tr><td>{escape(label)}</td><td>{escape(value)}</td></tr>"
        for label, value in rows
    )
    return f"""<div>
  <h2>Pipeline Run Metrics</h2>
  <table><tbody>{items}</tbody></table>
</div>"""


def as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def render_sample_table(records: list[dict[str, Any]], limit: int = 10) -> str:
    rows = []
    for record in records[-limit:][::-1]:
        rows.append(
            "<tr>"
            f"<td>{escape(record.get('record_type'))}</td>"
            f"<td>{escape(record.get('extracted_from'))}</td>"
            f"<td>{escape(record.get('source_name'))}</td>"
            f"<td>{escape(record.get('is_multimodal'))}</td>"
            f"<td>{escape(', '.join(record.get('validation_errors') or []))}</td>"
            f"<td>{escape(shorten(record.get('text')))}</td>"
            "</tr>"
        )

    return f"""<table>
  <thead>
    <tr>
      <th>Type</th>
      <th>Extractor</th>
      <th>Source</th>
      <th>Multimodal</th>
      <th>Errors</th>
      <th>Text Preview</th>
    </tr>
  </thead>
  <tbody>{"".join(rows)}</tbody>
</table>"""


def shorten(value: object, max_length: int = 150) -> str:
    text = str(value or "")
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def write_dashboard(
    input_path: Path, output_path: Path, metrics_path: Path | None = None
) -> Path:
    records = load_records(input_path)
    resolved_metrics_path = metrics_path or latest_metrics_path()
    run_metrics = load_metrics(resolved_metrics_path) if resolved_metrics_path else {}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_dashboard(records, build_metrics(records), run_metrics),
        encoding="utf-8",
    )
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the multimodal ETL KPI HTML dashboard."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Processed records JSON path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output HTML dashboard path.",
    )
    parser.add_argument(
        "--metrics",
        type=Path,
        default=None,
        help="Optional structured metrics JSON path. Defaults to the latest metrics file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = write_dashboard(args.input, args.output, args.metrics)
    print(f"Dashboard written to {output_path}")


if __name__ == "__main__":
    main()
