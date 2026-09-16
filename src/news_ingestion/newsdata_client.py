from __future__ import annotations

import logging
from typing import Any

import requests

from news_ingestion.config import Settings
from news_ingestion.image_validation import is_accessible_image_url
from news_ingestion.models import RawArticle

logger = logging.getLogger(__name__)


class NewsDataClient:
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
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.query = query
        self.language = language
        self.category = category
        self.country = country
        self.max_pages = max_pages
        self.only_with_images = only_with_images
        self.validate_image_urls = validate_image_urls
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings: Settings, timeout: int = 30) -> NewsDataClient:
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
            timeout=timeout,
        )

    def fetch_articles(self) -> list[RawArticle]:
        articles: list[RawArticle] = []
        next_page: str | None = None

        for _ in range(self.max_pages):
            try:
                response = requests.get(
                    self.base_url,
                    params=self._build_params(next_page),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except requests.RequestException as exc:
                msg = "NewsData.io HTTP request failed."
                raise RuntimeError(msg) from exc
            except ValueError as exc:
                msg = "NewsData.io response was not valid JSON."
                raise RuntimeError(msg) from exc

            if payload.get("status") == "error":
                message = payload.get("results", {}).get("message") or payload.get(
                    "message"
                )
                raise RuntimeError(f"NewsData.io API error: {message}")

            articles.extend(
                self._raw_article_from_payload(item)
                for item in payload.get("results", [])
            )

            next_page = payload.get("nextPage")
            if not next_page:
                break

        if self.only_with_images:
            articles = [article for article in articles if article.is_multimodal]

        if self.validate_image_urls:
            articles = self._filter_accessible_images(articles)

        return articles

    def _filter_accessible_images(self, articles: list[RawArticle]) -> list[RawArticle]:
        valid_articles: list[RawArticle] = []
        for article in articles:
            if is_accessible_image_url(article.image_url):
                valid_articles.append(article)
            else:
                logger.warning(
                    "Skipping article with inaccessible image: %s", article.link
                )
        return valid_articles

    def _build_params(self, next_page: str | None = None) -> dict[str, str]:
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
            extracted_from="newsdata.io",
            raw_payload=payload,
        )
