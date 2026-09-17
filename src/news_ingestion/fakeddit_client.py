from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from news_ingestion.config import Settings
from news_ingestion.image_validation import is_accessible_image_url
from news_ingestion.models import RawArticle

logger = logging.getLogger(__name__)


class FakedditClient:
    def __init__(
        self,
        dataset_dir: Path,
        files: list[str],
        max_records: int,
        only_multimodal: bool,
        validate_image_urls: bool,
    ) -> None:
        self.dataset_dir = dataset_dir
        self.files = files
        self.max_records = max_records
        self.only_multimodal = only_multimodal
        self.validate_image_urls = validate_image_urls

    @classmethod
    def from_settings(cls, settings: Settings) -> FakedditClient:
        return cls(
            dataset_dir=settings.fakeddit.dataset_dir,
            files=settings.fakeddit.files,
            max_records=settings.fakeddit.max_records,
            only_multimodal=settings.fakeddit.only_multimodal,
            validate_image_urls=settings.fakeddit.validate_image_urls,
        )

    def fetch_articles(self) -> list[RawArticle]:
        articles: list[RawArticle] = []

        for payload in self._iter_payloads():
            article = self._raw_article_from_payload(payload)
            if self.only_multimodal and not article.is_multimodal:
                continue
            if self.validate_image_urls and not is_accessible_image_url(
                article.image_url
            ):
                logger.warning(
                    "Skipping Fakeddit row with inaccessible image",
                    extra={
                        "source": "fakeddit",
                        "source_record_id": article.article_id,
                    },
                )
                continue

            articles.append(article)
            if len(articles) >= self.max_records:
                break

        return articles

    def _iter_payloads(self):
        for file_name in self.files:
            file_path = self.dataset_dir / file_name
            if not file_path.exists():
                msg = f"Fakeddit TSV file not found: {file_path}"
                raise FileNotFoundError(msg)
            with file_path.open(encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file, delimiter="\t")
                if reader.fieldnames is None:
                    msg = f"Fakeddit TSV file has no header: {file_path}"
                    raise ValueError(msg)
                for row in reader:
                    payload: dict[str, Any] = dict(row)
                    payload["file_name"] = file_name
                    yield payload

    def _raw_article_from_payload(self, payload: dict[str, Any]) -> RawArticle:
        post_id = self._first_value(payload, "id", "post_id")
        image_url = self._first_value(payload, "image_url", "image_url_processed")
        text = self._first_value(payload, "title", "clean_title", "text")
        label = self._first_value(payload, "2_way_label", "3_way_label", "6_way_label")

        return RawArticle(
            article_id=post_id,
            title=text,
            link=self._first_value(payload, "url", "permalink"),
            description=None,
            content=text,
            image_url=image_url,
            published_at=None,
            source_id=self._first_value(payload, "subreddit"),
            source_name=self._first_value(payload, "subreddit"),
            language=None,
            country=[],
            category=[label] if label else [],
            extracted_from="fakeddit",
            raw_payload=payload,
        )

    def _first_value(self, payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None
