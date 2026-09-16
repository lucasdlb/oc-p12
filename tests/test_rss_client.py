import sys
from types import SimpleNamespace

from news_ingestion.rss_client import RssClient


def test_fetch_articles_maps_rss_entries_and_filters_images(monkeypatch):
    calls = []

    def fake_parse(feed_url):
        calls.append(feed_url)
        return {
            "feed": {"title": "Example Climate Feed"},
            "entries": [
                {
                    "id": "entry-1",
                    "title": "Climate story",
                    "link": "https://example.com/climate-story",
                    "summary": "A climate summary.",
                    "published": "Fri, 04 Sep 2026 12:00:00 GMT",
                    "media_content": [
                        {
                            "url": "https://example.com/image.jpg",
                            "type": "image/jpeg",
                        }
                    ],
                    "tags": [{"term": "climate"}],
                },
                {
                    "id": "entry-2",
                    "title": "Text-only story",
                    "link": "https://example.com/text-only",
                    "summary": "No image.",
                },
            ],
        }

    monkeypatch.setitem(sys.modules, "feedparser", SimpleNamespace(parse=fake_parse))

    client = RssClient(
        feeds=["https://example.com/feed.xml"],
        max_records_per_feed=10,
        only_with_images=True,
        validate_image_urls=False,
    )

    articles = client.fetch_articles()

    assert len(articles) == 1
    assert articles[0].article_id == "entry-1"
    assert articles[0].title == "Climate story"
    assert articles[0].link == "https://example.com/climate-story"
    assert articles[0].description == "A climate summary."
    assert articles[0].image_url == "https://example.com/image.jpg"
    assert articles[0].published_at == "Fri, 04 Sep 2026 12:00:00 GMT"
    assert articles[0].source_id == "example.com"
    assert articles[0].source_name == "Example Climate Feed"
    assert articles[0].category == ["climate"]
    assert articles[0].extracted_from == "rss"
    assert articles[0].raw_payload["feed_url"] == "https://example.com/feed.xml"
    assert calls == ["https://example.com/feed.xml"]


def test_fetch_articles_skips_failed_rss_feed(monkeypatch):
    def fake_parse(feed_url):
        if "bad" in feed_url:
            raise RuntimeError("bad feed")
        return {
            "feed": {"title": "Good Feed"},
            "entries": [
                {
                    "id": "entry-1",
                    "title": "Climate story",
                    "link": "https://example.com/climate-story",
                    "summary": "A climate summary.",
                    "media_content": [{"url": "https://example.com/image.jpg"}],
                }
            ],
        }

    monkeypatch.setitem(sys.modules, "feedparser", SimpleNamespace(parse=fake_parse))

    client = RssClient(
        feeds=["https://example.com/bad.xml", "https://example.com/good.xml"],
        max_records_per_feed=10,
        only_with_images=True,
        validate_image_urls=False,
    )

    articles = client.fetch_articles()

    assert len(articles) == 1
    assert articles[0].article_id == "entry-1"
