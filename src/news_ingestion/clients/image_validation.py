"""Helpers for validating image URL format and accessibility."""

from __future__ import annotations

import requests

from news_ingestion.url_validation import has_valid_image_url_format


def check_image_url_accessibility(image_url: str | None, timeout: int = 10) -> bool:
    """Return whether an image URL responds successfully with image content."""
    if not has_valid_image_url_format(image_url):
        return False
    checked_image_url = image_url or ""

    try:
        response = requests.head(
            checked_image_url, allow_redirects=True, timeout=timeout
        )
        if response.status_code == 405:
            response = requests.get(
                checked_image_url,
                allow_redirects=True,
                stream=True,
                timeout=timeout,
            )
        response.raise_for_status()
    except requests.RequestException:
        return False

    content_type = response.headers.get("content-type", "").lower()
    return content_type.startswith("image/")
