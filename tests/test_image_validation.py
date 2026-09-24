from news_ingestion.clients.image_validation import (
    check_image_url_accessibility,
    has_valid_image_url_format,
)


def test_has_valid_image_url_format_checks_scheme_and_image_shape():
    assert has_valid_image_url_format("https://example.com/image.jpg") is True
    assert has_valid_image_url_format("https://example.com/image?id=1") is True
    assert has_valid_image_url_format("ftp://example.com/image.jpg") is False
    assert has_valid_image_url_format("not-a-url") is False


def test_check_image_url_accessibility_checks_content_type(monkeypatch):
    class Response:
        def __init__(self) -> None:
            self.status_code = 200
            self.headers = {"content-type": "image/jpeg"}

        def raise_for_status(self) -> None:
            return None

    def fake_head(url, allow_redirects, timeout):
        return Response()

    monkeypatch.setattr(
        "news_ingestion.clients.image_validation.requests.head", fake_head
    )

    assert check_image_url_accessibility("https://example.com/image.jpg") is True
