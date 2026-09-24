"""Climate-FEVER client for fetching raw claim records."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from news_ingestion.config import Settings
from news_ingestion.models import RawClaim
from news_ingestion.text import first_nonempty_string


class ClimateFeverClient:
    """Fetch claims from the Climate-FEVER dataset."""

    def __init__(
        self,
        dataset_name: str,
        split: str,
        max_records: int,
        hf_token: str | None = None,
    ) -> None:
        """Initialize a Climate-FEVER client with dataset settings."""
        self.dataset_name = dataset_name
        self.split = split
        self.max_records = max_records
        self.hf_token = hf_token

    @classmethod
    def from_settings(cls, settings: Settings) -> ClimateFeverClient:
        """Create a Climate-FEVER client from application settings."""
        return cls(
            dataset_name=settings.climate_fever.dataset_name,
            split=settings.climate_fever.split,
            max_records=settings.climate_fever.max_records,
            hf_token=(
                settings.hf_token.get_secret_value() if settings.hf_token else None
            ),
        )

    def fetch_claims(self) -> list[RawClaim]:
        """Fetch and normalize Climate-FEVER claims."""
        records = self._iter_dataset_records()
        claims: list[RawClaim] = []

        for record in records:
            claims.append(self._raw_claim_from_payload(record))
            if len(claims) >= self.max_records:
                break

        return claims

    def _iter_dataset_records(self) -> Iterable[dict[str, Any]]:
        """Iterate records from the configured Hugging Face dataset split."""
        from datasets import load_dataset

        try:
            dataset = load_dataset(
                self.dataset_name, split=self.split, token=self.hf_token
            )
        except Exception as exc:
            msg = f"Could not load Climate-FEVER dataset split '{self.split}'."
            raise RuntimeError(msg) from exc
        return (dict(record) for record in dataset)

    def _raw_claim_from_payload(self, payload: dict[str, Any]) -> RawClaim:
        """Convert a Climate-FEVER payload into a raw claim."""
        evidence = payload.get("evidences") or payload.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []

        return RawClaim(
            claim_id=first_nonempty_string(payload, "claim_id", "id"),
            claim=str(payload.get("claim") or ""),
            label=first_nonempty_string(payload, "claim_label", "label"),
            evidence=[item for item in evidence if isinstance(item, dict)],
            source_name="Climate-FEVER",
            language="en",
            country=None,
            extracted_from="climate_fever",
            raw_payload=payload,
        )
