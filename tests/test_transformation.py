import json

from news_ingestion.services.transformation import (
    clean_text,
    infer_record_type_from_filename,
    transform_article,
    transform_claim,
    transform_raw_files_to_json,
)


def test_clean_text_strips_and_collapses_whitespace():
    assert clean_text("  Climate\n\tchange   claim  ") == "Climate change claim"


def test_transform_article_builds_processed_multimodal_record():
    record = {
        "article_id": "abc-123",
        "title": "Climate title",
        "description": "Short description",
        "content": "Full content",
        "image_url": "https://example.com/image.jpg",
        "link": "https://example.com/article",
        "published_at": "2026-09-07",
        "source_name": "Example News",
        "extracted_from": "rss",
        "language": "en",
        "country": "US",
        "category": ["environment"],
        "raw_payload": {"2_way_label": "0"},
    }

    processed = transform_article(record)

    assert processed.record_id.startswith("article:rss:")
    assert processed.text == "Climate title\n\nShort description\n\nFull content"
    assert processed.is_multimodal is True
    assert processed.has_valid_image_url is True
    assert processed.label == "0"
    assert processed.country == ["US"]
    assert processed.validation_errors == []


def test_transform_article_reports_missing_image_url():
    processed = transform_article(
        {
            "article_id": "abc-123",
            "title": "Only text",
            "image_url": None,
            "extracted_from": "newsdata",
            "country": [],
            "category": [],
            "raw_payload": {},
        },
    )

    assert processed.is_multimodal is False
    assert processed.has_valid_image_url is False
    assert processed.validation_errors == ["missing_image_url"]


def test_transform_article_does_not_duplicate_identical_text_fields():
    processed = transform_article(
        {
            "article_id": "abc-123",
            "title": "Same text",
            "content": "Same text",
            "image_url": None,
            "extracted_from": "fakeddit",
        }
    )

    assert processed.text == "Same text"


def test_transform_claim_builds_processed_text_record():
    processed = transform_claim(
        {
            "claim_id": "claim-1",
            "claim": "  Claim text  ",
            "label": "MISINFORMATION",
            "evidence": [{"evidence": "one"}, {"evidence": "two"}],
            "source_name": "Dataset",
            "language": "en",
            "country": None,
            "extracted_from": "dataforgood",
        },
    )

    assert processed.record_id.startswith("claim:dataforgood:")
    assert processed.text == "Claim text"
    assert processed.label == "MISINFORMATION"
    assert processed.evidence_count == 2
    assert processed.is_multimodal is False
    assert processed.validation_errors == []


def test_fallback_record_id_is_stable_and_content_derived():
    base_record = {
        "article_id": None,
        "link": None,
        "title": "Stable title",
        "description": None,
        "content": "Stable content",
        "image_url": None,
        "published_at": "2026-09-23",
        "extracted_from": "rss",
        "country": [],
        "category": [],
        "raw_payload": {},
    }

    first = transform_article(base_record)
    second = transform_article(dict(base_record))
    changed = transform_article({**base_record, "content": "Different content"})

    assert first.record_id == second.record_id
    assert first.record_id != changed.record_id


def test_infer_record_type_from_file_name(tmp_path):
    assert infer_record_type_from_filename(tmp_path / "rss_articles.json") == "article"
    assert (
        infer_record_type_from_filename(tmp_path / "climate_fever_claims.json")
        == "claim"
    )
    assert infer_record_type_from_filename(tmp_path / "unknown.json") is None


def test_transform_raw_files_reads_only_explicit_artifacts(tmp_path):
    raw_dir = tmp_path / "raw"
    output_path = tmp_path / "processed" / "processed_records.json"
    raw_dir.mkdir()
    (raw_dir / "rss_articles.json").write_text(
        json.dumps(
            [
                {
                    "article_id": "article-1",
                    "title": "Title",
                    "description": None,
                    "content": None,
                    "image_url": "https://example.com/image.jpg",
                    "link": "https://example.com/article",
                    "extracted_from": "rss",
                    "country": [],
                    "category": [],
                    "raw_payload": {},
                }
            ]
        ),
        encoding="utf-8",
    )
    (raw_dir / "dataforgood_claims.json").write_text(
        json.dumps(
            [
                {
                    "claim_id": "claim-1",
                    "claim": "Claim",
                    "label": "CLEAN",
                    "evidence": [],
                    "extracted_from": "dataforgood",
                }
            ]
        ),
        encoding="utf-8",
    )
    (raw_dir / "stale_articles.json").write_text("[]", encoding="utf-8")

    result = transform_raw_files_to_json(
        [raw_dir / "rss_articles.json", raw_dir / "dataforgood_claims.json"],
        output_path,
    )
    saved_records = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.artifact_path == output_path
    assert result.record_count == 2
    assert [record["record_type"] for record in saved_records] == ["claim", "article"]
