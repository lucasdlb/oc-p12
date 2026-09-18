from __future__ import annotations

import logging
import time
from typing import Any

import requests

from news_ingestion.config import Settings
from news_ingestion.image_validation import is_accessible_image_url
from news_ingestion.models import RawArticle

logger = logging.getLogger(__name__)

TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


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
        max_retries: int,
        retry_backoff_seconds: list[int],
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
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
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
            max_retries=settings.gdelt.max_retries,
            retry_backoff_seconds=settings.gdelt.retry_backoff_seconds,
            timeout=timeout,
        )

    def fetch_articles(self) -> list[RawArticle]:
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

        if self.only_with_images:
            articles = [article for article in articles if article.is_multimodal]

        if self.validate_image_urls:
            articles = self._filter_accessible_images(articles)

        return articles

    def _fetch_payload(self) -> dict[str, Any]:
        attempts = self.max_retries + 1
        last_exception: requests.RequestException | ValueError | TypeError | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = requests.get(
                    self.base_url,
                    params=self._build_params(),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    msg = "GDELT response JSON root was not an object."
                    raise TypeError(msg)
                return payload
            except requests.RequestException as exc:
                last_exception = exc
                response = getattr(exc, "response", None)
                status_code = getattr(response, "status_code", None)
                if not self._should_retry(status_code, attempt):
                    self._log_request_failure(exc, attempt, status_code)
                    msg = "GDELT HTTP request failed."
                    raise RuntimeError(msg) from exc

                retry_after = self._retry_after_seconds(response)
                retry_delay = (
                    retry_after
                    if retry_after is not None
                    else self._retry_delay(attempt)
                )
                logger.warning(
                    "GDELT HTTP request will be retried",
                    extra={
                        "source": "gdelt",
                        "status_code": status_code,
                        "retry_attempt": attempt,
                        "max_retries": self.max_retries,
                        "retry_delay_seconds": retry_delay,
                        "retry_after": retry_after,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
                time.sleep(retry_delay)
            except (TypeError, ValueError) as exc:
                last_exception = exc
                msg = "GDELT response was not valid JSON."
                raise RuntimeError(msg) from exc

        msg = "GDELT HTTP request failed."
        raise RuntimeError(msg) from last_exception

    def _should_retry(self, status_code: int | None, attempt: int) -> bool:
        return status_code in TRANSIENT_STATUS_CODES and attempt <= self.max_retries

    def _retry_delay(self, attempt: int) -> int:
        if not self.retry_backoff_seconds:
            return 0
        index = min(attempt - 1, len(self.retry_backoff_seconds) - 1)
        return self.retry_backoff_seconds[index]

    def _retry_after_seconds(self, response: requests.Response | None) -> int | None:
        if response is None:
            return None
        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return None
        try:
            delay = int(retry_after)
        except ValueError:
            return None
        return max(delay, 0)

    def _log_request_failure(
        self,
        exc: requests.RequestException,
        attempt: int,
        status_code: int | None,
    ) -> None:
        logger.warning(
            "GDELT HTTP request failed",
            extra={
                "source": "gdelt",
                "status_code": status_code,
                "attempts": attempt,
                "max_retries": self.max_retries,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )

    def _filter_accessible_images(self, articles: list[RawArticle]) -> list[RawArticle]:
        valid_articles: list[RawArticle] = []
        for article in articles:
            if is_accessible_image_url(article.image_url):
                valid_articles.append(article)
            else:
                logger.warning(
                    "Skipping article with inaccessible image",
                    extra={"source": "gdelt", "source_url": article.link},
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
