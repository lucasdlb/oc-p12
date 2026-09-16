from __future__ import annotations

import logging
from typing import Any

import requests

from news_ingestion.config import Settings
from news_ingestion.image_validation import is_accessible_image_url
from news_ingestion.models import RawArticle

logger = logging.getLogger(__name__)


class GdeltClient:
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
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url
        self.query = query
        self.mode = mode
        self.response_format = response_format
        self.max_records = max_records
        self.sort = sort
        self.language = language
        self.only_with_images = only_with_images
        self.validate_image_urls = validate_image_urls
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings: Settings, timeout: int = 30) -> GdeltClient:
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
            timeout=timeout,
        )

    def fetch_articles(self) -> list[RawArticle]:
        try:
            response = requests.get(
                self.base_url,
                params=self._build_params(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            msg = "GDELT HTTP request failed."
            raise RuntimeError(msg) from exc
        except ValueError as exc:
            msg = "GDELT response was not valid JSON."
            raise RuntimeError(msg) from exc

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

    def _build_params(self) -> dict[str, str]:
        return {
            "query": self.query,
            "mode": self.mode,
            "format": self.response_format,
            "maxrecords": str(self.max_records),
            "sort": self.sort,
        }

    def _raw_article_from_payload(self, payload: dict[str, Any]) -> RawArticle:
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
