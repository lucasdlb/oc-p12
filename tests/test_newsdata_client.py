import pytest
import requests

from news_ingestion.newsdata_client import NewsDataClient


def test_fetch_articles_uses_explicit_client_config(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "status": "success",
                "results": [
                    {
                        "article_id": "article-1",
                        "title": "Climate story",
                        "image_url": "https://example.com/image.jpg",
                    }
                ],
            }

    def fake_get(url, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        return Response()

    monkeypatch.setattr("news_ingestion.newsdata_client.requests.get", fake_get)

    client = NewsDataClient(
        api_key="pub_test_key",
        base_url="https://newsdata.example/news",
        query="climate change",
        language="en",
        category="environment",
        country="ca",
        max_pages=1,
        only_with_images=True,
        validate_image_urls=False,
        timeout=10,
    )

    articles = client.fetch_articles()

    assert len(articles) == 1
    assert articles[0].extracted_from == "newsdata.io"
    assert articles[0].raw_payload["article_id"] == "article-1"
    assert calls == [
        {
            "url": "https://newsdata.example/news",
            "params": {
                "apikey": "pub_test_key",
                "q": "climate change",
                "language": "en",
                "category": "environment",
                "country": "ca",
            },
            "timeout": 10,
        }
    ]


def test_fetch_articles_wraps_newsdata_http_errors(monkeypatch):
    def fake_get(url, params, timeout):
        raise requests.Timeout("timed out")

    monkeypatch.setattr("news_ingestion.newsdata_client.requests.get", fake_get)

    client = NewsDataClient(
        api_key="pub_test_key",
        base_url="https://newsdata.example/news",
        query="climate change",
        language="en",
        category="environment",
        country=None,
        max_pages=1,
        only_with_images=True,
        validate_image_urls=False,
        timeout=10,
    )

    with pytest.raises(RuntimeError, match="NewsData.io HTTP request failed"):
        client.fetch_articles()


def test_fetch_articles_can_validate_image_urls(monkeypatch):
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "status": "success",
                "results": [
                    {
                        "article_id": "article-1",
                        "title": "Climate story",
                        "image_url": "https://example.com/image.jpg",
                    },
                    {
                        "article_id": "article-2",
                        "title": "Broken image story",
                        "image_url": "https://example.com/broken.jpg",
                    },
                ],
            }

    def fake_get(url, params, timeout):
        return Response()

    def fake_image_check(image_url):
        return image_url == "https://example.com/image.jpg"

    monkeypatch.setattr("news_ingestion.newsdata_client.requests.get", fake_get)
    monkeypatch.setattr(
        "news_ingestion.newsdata_client.is_accessible_image_url",
        fake_image_check,
    )

    client = NewsDataClient(
        api_key="pub_test_key",
        base_url="https://newsdata.example/news",
        query="climate change",
        language="en",
        category="environment",
        country=None,
        max_pages=1,
        only_with_images=True,
        validate_image_urls=True,
        timeout=10,
    )

    articles = client.fetch_articles()

    assert [article.article_id for article in articles] == ["article-1"]
