"""Fakeddit client for reading local raw article records."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from news_ingestion.clients.normalization import is_article_eligible
from news_ingestion.config import Settings
from news_ingestion.models import RawArticle
from news_ingestion.text import first_nonempty_string

logger = logging.getLogger(__name__)


class FakedditClient:
    """Read article-like records from local Fakeddit TSV files."""

    def __init__(
        self,
        dataset_dir: Path,
        files: list[str],
        max_records: int,
        only_multimodal: bool,
        validate_image_urls: bool,
    ) -> None:
        """Initialize a Fakeddit client with local dataset settings."""
        self.dataset_dir = dataset_dir
        self.files = files
        self.max_records = max_records
        self.only_multimodal = only_multimodal
        self.validate_image_urls = validate_image_urls

    @classmethod
    def from_settings(cls, settings: Settings) -> FakedditClient:
        """Create a Fakeddit client from application settings."""
        return cls(
            dataset_dir=settings.fakeddit.dataset_dir,
            files=settings.fakeddit.files,
            max_records=settings.fakeddit.max_records,
            only_multimodal=settings.fakeddit.only_multimodal,
            validate_image_urls=settings.fakeddit.validate_image_urls,
        )

    def load_articles(self) -> list[RawArticle]:
        """Read and normalize Fakeddit article records."""
        self._validate_input_files()
        articles: list[RawArticle] = []

        for payload in self._iter_payloads():
            article = self._raw_article_from_payload(payload)
            if not is_article_eligible(
                "fakeddit",
                article,
                logger,
                only_multimodal=self.only_multimodal,
                validate_image_url=self.validate_image_urls,
            ):
                continue

            articles.append(article)
            if len(articles) >= self.max_records:
                break

        return articles

    def _validate_input_files(self) -> None:
        """Validate every configured input before reading any records."""
        for file_name in self.files:
            file_path = self.dataset_dir / file_name
            if not file_path.exists():
                msg = f"Fakeddit TSV file not found: {file_path}"
                raise FileNotFoundError(msg)

    def _iter_payloads(self):
        """Yield raw Fakeddit rows from configured TSV files."""
        for file_name in self.files:
            file_path = self.dataset_dir / file_name
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
        """Convert a Fakeddit row payload into a raw article."""
        post_id = first_nonempty_string(payload, "id", "post_id")
        image_url = first_nonempty_string(payload, "image_url", "image_url_processed")
        text = first_nonempty_string(payload, "title", "clean_title", "text")
        label = first_nonempty_string(
            payload, "2_way_label", "3_way_label", "6_way_label"
        )

        return RawArticle(
            article_id=post_id,
            title=text,
            link=first_nonempty_string(payload, "url", "permalink"),
            description=None,
            content=None,
            image_url=image_url,
            published_at=None,
            source_id=first_nonempty_string(payload, "subreddit"),
            source_name=first_nonempty_string(payload, "subreddit"),
            language=None,
            country=[],
            category=[label] if label else [],
            extracted_from="fakeddit",
            raw_payload=payload,
        )
