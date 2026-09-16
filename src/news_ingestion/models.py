from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RawArticle:
    article_id: str | None
    title: str | None
    link: str | None
    description: str | None
    content: str | None
    image_url: str | None
    published_at: str | None
    source_id: str | None
    source_name: str | None
    language: str | None
    country: list[str]
    category: list[str]
    extracted_from: str
    raw_payload: dict[str, Any]

    @property
    def has_text(self) -> bool:
        return any((self.title, self.description, self.content))

    @property
    def is_multimodal(self) -> bool:
        return self.has_text and bool(self.image_url)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RawClaim:
    claim_id: str | None
    claim: str
    label: str | None
    evidence: list[dict[str, Any]]
    source_name: str | None
    language: str | None
    country: str | None
    extracted_from: str
    raw_payload: dict[str, Any]

    @property
    def has_text(self) -> bool:
        return bool(self.claim.strip())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
