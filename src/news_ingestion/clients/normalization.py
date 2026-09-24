"""Shared source normalization and filtering helpers."""

from __future__ import annotations

import logging

from news_ingestion.clients.image_validation import check_image_url_accessibility
from news_ingestion.models import RawArticle


def is_article_eligible(
    source: str,
    article: RawArticle,
    logger: logging.Logger,
    *,
    only_multimodal: bool,
    validate_image_url: bool,
) -> bool:
    """Return whether an article satisfies configured content and image checks."""
    if only_multimodal and not article.is_multimodal:
        return False
    if not validate_image_url or check_image_url_accessibility(article.image_url):
        return True
    logger.warning(
        "Skipping article with inaccessible image",
        extra={
            "source": source,
            "source_record_id": article.article_id,
            "source_url": article.link,
        },
    )
    return False


def filter_accessible_articles(
    source: str,
    articles: list[RawArticle],
    logger: logging.Logger,
) -> list[RawArticle]:
    """Return only articles whose image URLs are accessible."""
    return [
        article
        for article in articles
        if is_article_eligible(
            source,
            article,
            logger,
            only_multimodal=False,
            validate_image_url=True,
        )
    ]
