"""Pure URL validation helpers."""

from urllib.parse import urlparse

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg")


def has_valid_image_url_format(image_url: str | None) -> bool:
    """Return whether a URL looks like a usable HTTP image URL."""
    if not image_url:
        return False

    parsed_url = urlparse(image_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return False

    path = parsed_url.path.lower()
    return path.endswith(IMAGE_EXTENSIONS) or bool(parsed_url.query)
