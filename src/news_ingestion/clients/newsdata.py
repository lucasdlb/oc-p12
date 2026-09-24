"""NewsData.io client for fetching raw article records."""

from __future__ import annotations

import logging
from typing import Any

from news_ingestion.clients.http import get_json_with_retries
from news_ingestion.clients.normalization import is_article_eligible
from news_ingestion.config import Settings
from news_ingestion.models import RawArticle

logger = logging.getLogger(__name__)


class NewsDataClient:
    """Fetch articles from the NewsData.io API."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        query: str,
        language: str,
        category: str,
        country: str | None,
        max_pages: int,
        only_with_images: bool,
        validate_image_urls: bool,
        max_retries: int = 5,
        retry_backoff_seconds: list[int] | None = None,
        timeout: int = 30,
    ) -> None:
        """Initialize a NewsData.io client with request and filter settings."""
        self.api_key = api_key
        self.base_url = base_url
        self.query = query
        self.language = language
        self.category = category
        self.country = country
        self.max_pages = max_pages
        self.only_with_images = only_with_images
        self.validate_image_urls = validate_image_urls
        self.max_retries = max_retries
        self.retry_backoff_seconds = (
            [5, 10, 15, 20, 25]
            if retry_backoff_seconds is None
            else retry_backoff_seconds
        )
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings: Settings, timeout: int = 30) -> NewsDataClient:
        """Create a NewsData.io client from application settings."""
        if settings.news_data_api_key is None:
            msg = "NEWS_DATA_API_KEY is required to fetch NewsData.io articles."
            raise RuntimeError(msg)

        return cls(
            api_key=settings.news_data_api_key.get_secret_value(),
            base_url=settings.newsdata.base_url,
            query=settings.newsdata.query,
            language=settings.newsdata.language,
            category=settings.newsdata.category,
            country=settings.newsdata.country,
            max_pages=settings.newsdata.max_pages,
            only_with_images=settings.newsdata.only_with_images,
            validate_image_urls=settings.newsdata.validate_image_urls,
            max_retries=settings.newsdata.max_retries,
            retry_backoff_seconds=settings.newsdata.retry_backoff_seconds,
            timeout=timeout,
        )

    def fetch_articles(self) -> list[RawArticle]:
        """Fetch and normalize NewsData.io articles."""
        articles: list[RawArticle] = []
        next_page: str | None = None

        for _ in range(self.max_pages):
            payload = get_json_with_retries(
                source="NewsData.io",
                url=self.base_url,
                params=self._build_params(next_page),
                timeout=self.timeout,
                max_retries=self.max_retries,
                retry_backoff_seconds=self.retry_backoff_seconds,
                logger=logger,
            )

            if payload.get("status") == "error":
                message = payload.get("results", {}).get("message") or payload.get(
                    "message"
                )
                logger.error(
                    "NewsData.io API returned an error",
                    extra={"source": "newsdata", "error_message": message},
                )
                raise RuntimeError(f"NewsData.io API error: {message}")

            articles.extend(
                self._raw_article_from_payload(item)
                for item in payload.get("results", [])
            )

            next_page = payload.get("nextPage")
            if not next_page:
                break

        return [
            article
            for article in articles
            if is_article_eligible(
                "newsdata",
                article,
                logger,
                only_multimodal=self.only_with_images,
                validate_image_url=self.validate_image_urls,
            )
        ]

    def _build_params(self, next_page: str | None = None) -> dict[str, str]:
        """Build request parameters for a NewsData.io page."""
        params = {
            "apikey": self.api_key,
            "q": self.query,
            "language": self.language,
            "category": self.category,
        }

        if self.country:
            params["country"] = self.country

        if next_page:
            params["page"] = next_page

        return params

    def _raw_article_from_payload(self, payload: dict[str, Any]) -> RawArticle:
        """Convert a NewsData.io result payload into a raw article."""
        return RawArticle(
            article_id=payload.get("article_id"),
            title=payload.get("title"),
            link=payload.get("link"),
            description=payload.get("description"),
            content=payload.get("content"),
            image_url=payload.get("image_url"),
            published_at=payload.get("pubDate"),
            source_id=payload.get("source_id"),
            source_name=payload.get("source_name"),
            language=payload.get("language"),
            country=payload.get("country") or [],
            category=payload.get("category") or [],
            extracted_from="newsdata",
            raw_payload=payload,
        )
