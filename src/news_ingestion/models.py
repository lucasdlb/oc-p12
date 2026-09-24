"""Source and processed record contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Literal

RecordType = Literal["article", "claim"]


@dataclass(frozen=True)
class RawArticle:
    """Article record extracted from a news-like source."""

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
        """Return whether the article has any textual content."""
        return any(
            value is not None and bool(value.strip())
            for value in (self.title, self.description, self.content)
        )

    @property
    def is_multimodal(self) -> bool:
        """Return whether the article has both text and an image URL."""
        return self.has_text and bool(self.image_url)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the article as a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class RawClaim:
    """Claim record extracted from a fact-checking or dataset source."""

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
        """Return whether the claim text is non-empty."""
        return bool(self.claim.strip())

    def to_dict(self) -> dict[str, Any]:
        """Serialize the claim as a plain dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class ProcessedRecord:
    """Normalized record ready for metrics, storage, and loading."""

    record_id: str
    record_type: RecordType
    source_record_id: str | None
    title: str | None
    text: str
    image_url: str | None
    source_url: str | None
    published_at: str | None
    source_name: str | None
    extracted_from: str
    language: str | None
    country: list[str]
    category: list[str]
    label: str | None
    evidence_count: int
    text_length: int
    word_count: int
    is_multimodal: bool
    has_valid_image_url: bool
    validation_errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the processed record as a plain dictionary."""
        return asdict(self)


PROCESSED_RECORD_COLUMNS = tuple(field.name for field in fields(ProcessedRecord))
