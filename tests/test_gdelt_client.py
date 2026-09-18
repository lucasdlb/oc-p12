import pytest
import requests

from news_ingestion.gdelt_client import GdeltClient


def test_fetch_articles_uses_gdelt_config_and_maps_multimodal_records(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "articles": [
                    {
                        "url": "https://example.com/climate-story",
                        "title": "Climate story",
                        "seendate": "20260904T123000Z",
                        "socialimage": "https://example.com/image.jpg",
                        "domain": "example.com",
                        "language": "English",
                        "sourcecountry": "US",
                    },
                    {
                        "url": "https://example.com/no-image",
                        "title": "No image story",
                        "domain": "example.com",
                        "language": "English",
                    },
                    {
                        "url": "https://example.fr/story",
                        "title": "French story",
                        "socialimage": "https://example.fr/image.jpg",
                        "domain": "example.fr",
                        "language": "French",
                    },
                ]
            }

    def fake_get(url, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        return Response()

    monkeypatch.setattr("news_ingestion.gdelt_client.requests.get", fake_get)

    client = GdeltClient(
        base_url="https://api.gdelt.example/doc",
        query="climate change",
        mode="artlist",
        response_format="json",
        max_records=25,
        sort="datedesc",
        language="English",
        only_with_images=True,
        validate_image_urls=False,
        max_retries=5,
        retry_backoff_seconds=[5, 10, 15, 20, 25],
        timeout=10,
    )

    articles = client.fetch_articles()

    assert len(articles) == 1
    assert articles[0].article_id == "https://example.com/climate-story"
    assert articles[0].title == "Climate story"
    assert articles[0].image_url == "https://example.com/image.jpg"
    assert articles[0].published_at == "20260904T123000Z"
    assert articles[0].source_name == "example.com"
    assert articles[0].country == ["US"]
    assert articles[0].extracted_from == "gdelt"
    assert articles[0].raw_payload["url"] == "https://example.com/climate-story"
    assert calls == [
        {
            "url": "https://api.gdelt.example/doc",
            "params": {
                "query": "climate change",
                "mode": "artlist",
                "format": "json",
                "maxrecords": "25",
                "sort": "datedesc",
            },
            "timeout": 10,
        }
    ]


def test_fetch_articles_retries_transient_gdelt_errors(monkeypatch):
    calls = []
    sleeps = []

    class Response:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code
            self.headers: dict[str, str] = {}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise requests.HTTPError("too many requests", response=self)

        def json(self) -> dict[str, object]:
            return {
                "articles": [
                    {
                        "url": "https://example.com/climate-story",
                        "title": "Climate story",
                        "socialimage": "https://example.com/image.jpg",
                        "language": "English",
                    }
                ]
            }

    def fake_get(url, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        if len(calls) == 1:
            return Response(429)
        return Response(200)

    monkeypatch.setattr("news_ingestion.gdelt_client.requests.get", fake_get)
    monkeypatch.setattr("news_ingestion.gdelt_client.time.sleep", sleeps.append)

    client = GdeltClient(
        base_url="https://api.gdelt.example/doc",
        query="climate change",
        mode="artlist",
        response_format="json",
        max_records=25,
        sort="datedesc",
        language="English",
        only_with_images=True,
        validate_image_urls=False,
        max_retries=5,
        retry_backoff_seconds=[5, 10, 15, 20, 25],
        timeout=10,
    )

    articles = client.fetch_articles()

    assert len(articles) == 1
    assert len(calls) == 2
    assert sleeps == [5]


def test_fetch_articles_uses_retry_after_header(monkeypatch):
    calls = []
    sleeps = []

    class Response:
        def __init__(self) -> None:
            self.status_code = 429
            self.headers = {"Retry-After": "7"}

        def raise_for_status(self) -> None:
            raise requests.HTTPError("too many requests", response=self)

    def fake_get(url, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        return Response()

    monkeypatch.setattr("news_ingestion.gdelt_client.requests.get", fake_get)
    monkeypatch.setattr("news_ingestion.gdelt_client.time.sleep", sleeps.append)

    client = GdeltClient(
        base_url="https://api.gdelt.example/doc",
        query="climate change",
        mode="artlist",
        response_format="json",
        max_records=25,
        sort="datedesc",
        language="English",
        only_with_images=True,
        validate_image_urls=False,
        max_retries=1,
        retry_backoff_seconds=[5],
        timeout=10,
    )

    with pytest.raises(RuntimeError, match="GDELT HTTP request failed"):
        client.fetch_articles()

    assert len(calls) == 2
    assert sleeps == [7]


def test_fetch_articles_does_not_retry_non_transient_gdelt_errors(monkeypatch):
    calls = []
    sleeps = []

    class Response:
        def __init__(self) -> None:
            self.status_code = 400
            self.headers: dict[str, str] = {}

        def raise_for_status(self) -> None:
            raise requests.HTTPError("bad request", response=self)

    def fake_get(url, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        return Response()

    monkeypatch.setattr("news_ingestion.gdelt_client.requests.get", fake_get)
    monkeypatch.setattr("news_ingestion.gdelt_client.time.sleep", sleeps.append)

    client = GdeltClient(
        base_url="https://api.gdelt.example/doc",
        query="climate change",
        mode="artlist",
        response_format="json",
        max_records=25,
        sort="datedesc",
        language="English",
        only_with_images=True,
        validate_image_urls=False,
        max_retries=5,
        retry_backoff_seconds=[5, 10, 15, 20, 25],
        timeout=10,
    )

    with pytest.raises(RuntimeError, match="GDELT HTTP request failed"):
        client.fetch_articles()

    assert len(calls) == 1
    assert sleeps == []
