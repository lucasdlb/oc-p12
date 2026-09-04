from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests

from news_ingestion.config import Settings


@dataclass(frozen=True)
class NewsArticle:
    article_id: str | None
    title: str | None
    link: str | None
    description: str | None
    content: str | None
    image_url: str | None
    published_at: str | None
    source_id: str | None
    source_name: str | None
    language: str | None
    country: list[str]
    category: list[str]
    extracted_from: str

    @classmethod
    def from_api_payload(cls, payload: dict[str, Any]) -> NewsArticle:
        return cls(
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
        )

    @property
    def has_text(self) -> bool:
        return any((self.title, self.description, self.content))

    @property
    def is_multimodal(self) -> bool:
        return self.has_text and bool(self.image_url)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings: Settings, timeout: int = 30) -> NewsDataClient:
        return cls(
            api_key=settings.news_data_api_key.get_secret_value(),
            base_url=settings.news_data_base_url,
            query=settings.news_data_query,
            language=settings.news_data_language,
            category=settings.news_data_category,
            country=settings.news_data_country,
            max_pages=settings.news_data_max_pages,
            only_with_images=settings.news_data_only_with_images,
            timeout=timeout,
        )

    def fetch_articles(self) -> list[NewsArticle]:
        articles: list[NewsArticle] = []
        next_page: str | None = None

        for _ in range(self.max_pages):
            response = requests.get(
                self.base_url,
                params=self._build_params(next_page),
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()

            if payload.get("status") == "error":
                message = payload.get("results", {}).get("message") or payload.get(
                    "message"
                )
                raise RuntimeError(f"NewsData.io API error: {message}")

            articles.extend(
                NewsArticle.from_api_payload(item)
                for item in payload.get("results", [])
            )

            next_page = payload.get("nextPage")
            if not next_page:
                break

        if self.only_with_images:
            return [article for article in articles if article.is_multimodal]

        return articles

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


def save_articles(articles: list[NewsArticle], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serializable_articles = [article.to_dict() for article in articles]
    output_path.write_text(
        json.dumps(serializable_articles, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
