from __future__ import annotations

from urllib.parse import urlparse

import requests

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg")


def has_valid_image_url_format(image_url: str | None) -> bool:
    if not image_url:
        return False

    parsed_url = urlparse(image_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return False

    path = parsed_url.path.lower()
    return path.endswith(IMAGE_EXTENSIONS) or bool(parsed_url.query)


def is_accessible_image_url(image_url: str | None, timeout: int = 10) -> bool:
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
