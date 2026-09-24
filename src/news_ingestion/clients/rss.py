"""RSS client for fetching raw article records."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from news_ingestion.clients.normalization import is_article_eligible
from news_ingestion.config import Settings
from news_ingestion.models import RawArticle
from news_ingestion.text import coerce_nonempty_string, first_nonempty_string

logger = logging.getLogger(__name__)


class RssClient:
    """Fetch articles from configured RSS feeds."""

    def __init__(
        self,
        feeds: list[str],
        max_records_per_feed: int,
        only_with_images: bool,
        validate_image_urls: bool,
    ) -> None:
        """Initialize an RSS client with feed and filtering settings."""
        self.feeds = feeds
        self.max_records_per_feed = max_records_per_feed
        self.only_with_images = only_with_images
        self.validate_image_urls = validate_image_urls

    @classmethod
    def from_settings(cls, settings: Settings) -> RssClient:
        """Create an RSS client from application settings."""
        return cls(
            feeds=settings.rss.feeds,
            max_records_per_feed=settings.rss.max_records_per_feed,
            only_with_images=settings.rss.only_with_images,
            validate_image_urls=settings.rss.validate_image_urls,
        )

    def fetch_articles(self) -> list[RawArticle]:
        """Fetch and normalize articles from all configured RSS feeds."""
        articles: list[RawArticle] = []
        successful_feeds = 0

        for feed_url in self.feeds:
            try:
                feed_payload = self._parse_feed(feed_url)
            except Exception as exc:
                logger.exception(
                    "Skipping RSS feed after parse failure",
                    extra={
                        "source": "rss",
                        "feed_url": feed_url,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
                continue

            successful_feeds += 1

            if feed_payload.get("bozo"):
                logger.warning(
                    "RSS feed reported parsing issues",
                    extra={"source": "rss", "feed_url": feed_url},
                )

            feed_title = self._feed_title(feed_payload, feed_url)

            for entry in feed_payload.get("entries", [])[: self.max_records_per_feed]:
                if not isinstance(entry, dict):
                    continue

                article = self._raw_article_from_entry(entry, feed_url, feed_title)
                if not is_article_eligible(
                    "rss",
                    article,
                    logger,
                    only_multimodal=self.only_with_images,
                    validate_image_url=self.validate_image_urls,
                ):
                    continue
                articles.append(article)

        if successful_feeds == 0:
            msg = "All configured RSS feeds failed to load."
            raise RuntimeError(msg)
        return articles

    def _parse_feed(self, feed_url: str) -> dict[str, Any]:
        """Parse an RSS feed URL with feedparser."""
        import feedparser

        return dict(feedparser.parse(feed_url))

    def _raw_article_from_entry(
        self,
        entry: dict[str, Any],
        feed_url: str,
        feed_title: str,
    ) -> RawArticle:
        """Convert an RSS entry into a raw article."""
        link = coerce_nonempty_string(entry.get("link"))
        published_at = first_nonempty_string(entry, "published", "updated")
        tags = self._extract_tags(entry)

        return RawArticle(
            article_id=first_nonempty_string(entry, "id", "guid", "link"),
            title=coerce_nonempty_string(entry.get("title")),
            link=link,
            description=first_nonempty_string(entry, "summary", "description"),
            content=None,
            image_url=self._extract_image_url(entry),
            published_at=published_at,
            source_id=urlparse(feed_url).netloc,
            source_name=feed_title,
            language=coerce_nonempty_string(entry.get("language")),
            country=[],
            category=tags,
            extracted_from="rss",
            raw_payload={"feed_url": feed_url, **entry},
        )

    def _feed_title(self, feed_payload: dict[str, Any], feed_url: str) -> str:
        """Return a feed title or fallback host name."""
        feed = feed_payload.get("feed")
        if isinstance(feed, dict):
            title = coerce_nonempty_string(feed.get("title"))
            if title:
                return title
        return urlparse(feed_url).netloc

    def _extract_image_url(self, entry: dict[str, Any]) -> str | None:
        """Extract the first image URL from an RSS entry."""
        media_content = entry.get("media_content") or entry.get("media_thumbnail")
        image_url = self._image_url_from_media_list(media_content)
        if image_url:
            return image_url

        enclosures = entry.get("enclosures") or entry.get("links")
        return self._image_url_from_media_list(enclosures)

    def _image_url_from_media_list(self, media_items: object) -> str | None:
        """Extract an image URL from RSS media or enclosure items."""
        if not isinstance(media_items, list):
            return None

        for item in media_items:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "")
            url = coerce_nonempty_string(item.get("url") or item.get("href"))
            if url and (not item_type or item_type.startswith("image/")):
                return url
        return None

    def _extract_tags(self, entry: dict[str, Any]) -> list[str]:
        """Extract category tags from an RSS entry."""
        tags = entry.get("tags") or []
        if not isinstance(tags, list):
            return []

        extracted_tags: list[str] = []
        for tag in tags:
            if isinstance(tag, dict):
                term = coerce_nonempty_string(tag.get("term"))
                if term:
                    extracted_tags.append(term)
        return extracted_tags
