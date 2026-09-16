import json
from pathlib import Path

from news_ingestion.models import RawArticle, RawClaim


def save_raw_articles(articles: list[RawArticle], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serializable_articles = [article.to_dict() for article in articles]
    output_path.write_text(
        json.dumps(serializable_articles, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_raw_claims(claims: list[RawClaim], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serializable_claims = [claim.to_dict() for claim in claims]
    output_path.write_text(
        json.dumps(serializable_claims, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
