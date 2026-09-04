from __future__ import annotations

from news_ingestion.config import Settings
from news_ingestion.newsdata_client import NewsDataClient, save_articles


def main() -> None:
    settings = Settings()
    client = NewsDataClient.from_settings(settings)
    articles = client.fetch_articles()

    output_path = settings.raw_data_dir / "newsdata_articles.json"
    save_articles(articles, output_path)

    print(f"Fetched {len(articles)} multimodal NewsData.io articles.")
    print(f"Theme: {settings.news_data_query} / {settings.news_data_category}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
