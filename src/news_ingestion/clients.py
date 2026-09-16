from typing import Protocol

from news_ingestion.models import RawArticle, RawClaim


class ArticleSourceClient(Protocol):
    def fetch_articles(self) -> list[RawArticle]: ...


class ClaimSourceClient(Protocol):
    def fetch_claims(self) -> list[RawClaim]: ...
