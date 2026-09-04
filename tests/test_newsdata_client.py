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
        timeout=10,
    )

    articles = client.fetch_articles()

    assert len(articles) == 1
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
