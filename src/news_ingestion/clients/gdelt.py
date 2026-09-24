"""GDELT client for fetching raw article records."""

from __future__ import annotations

import logging
from typing import Any

from news_ingestion.clients.http import get_json_with_retries
from news_ingestion.clients.normalization import is_article_eligible
from news_ingestion.config import Settings
from news_ingestion.models import RawArticle

logger = logging.getLogger(__name__)


class GdeltClient:
    """Fetch articles from the GDELT document API."""

    def __init__(
        self,
        base_url: str,
        query: str,
        mode: str,
        response_format: str,
        max_records: int,
        sort: str,
        language: str | None,
        only_with_images: bool,
        validate_image_urls: bool,
        max_retries: int,
        retry_backoff_seconds: list[int],
        timeout: int = 30,
    ) -> None:
        """Initialize a GDELT client with request, retry, and filter settings."""
        self.base_url = base_url
        self.query = query
        self.mode = mode
        self.response_format = response_format
        self.max_records = max_records
        self.sort = sort
        self.language = language
        self.only_with_images = only_with_images
        self.validate_image_urls = validate_image_urls
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings: Settings, timeout: int = 30) -> GdeltClient:
        """Create a GDELT client from application settings."""
        return cls(
            base_url=settings.gdelt.base_url,
            query=settings.gdelt.query,
            mode=settings.gdelt.mode,
            response_format=settings.gdelt.response_format,
            max_records=settings.gdelt.max_records,
            sort=settings.gdelt.sort,
            language=settings.gdelt.language,
            only_with_images=settings.gdelt.only_with_images,
            validate_image_urls=settings.gdelt.validate_image_urls,
            max_retries=settings.gdelt.max_retries,
            retry_backoff_seconds=settings.gdelt.retry_backoff_seconds,
            timeout=timeout,
        )

    def fetch_articles(self) -> list[RawArticle]:
        """Fetch and normalize GDELT articles."""
        payload = self._fetch_payload()

        articles = [
            self._raw_article_from_payload(item) for item in payload.get("articles", [])
        ]

        if self.language:
            articles = [
                article
                for article in articles
                if article.language
                and article.language.lower() == self.language.lower()
            ]

        return [
            article
            for article in articles
            if is_article_eligible(
                "gdelt",
                article,
                logger,
                only_multimodal=self.only_with_images,
                validate_image_url=self.validate_image_urls,
            )
        ]

    def _fetch_payload(self) -> dict[str, Any]:
        """Fetch the GDELT response payload with retry handling."""
        return get_json_with_retries(
            source="GDELT",
            url=self.base_url,
            params=self._build_params(),
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_backoff_seconds=self.retry_backoff_seconds,
            logger=logger,
        )

    def _build_params(self) -> dict[str, str]:
        """Build request parameters for GDELT."""
        return {
            "query": self.query,
            "mode": self.mode,
            "format": self.response_format,
            "maxrecords": str(self.max_records),
            "sort": self.sort,
        }

    def _raw_article_from_payload(self, payload: dict[str, Any]) -> RawArticle:
        """Convert a GDELT article payload into a raw article."""
        source_country = payload.get("sourcecountry")
        return RawArticle(
            article_id=payload.get("url"),
            title=payload.get("title"),
            link=payload.get("url"),
            description=None,
            content=None,
            image_url=payload.get("socialimage"),
            published_at=payload.get("seendate"),
            source_id=payload.get("domain"),
            source_name=payload.get("domain"),
            language=payload.get("language"),
            country=[source_country] if source_country else [],
            category=[],
            extracted_from="gdelt",
            raw_payload=payload,
        )
