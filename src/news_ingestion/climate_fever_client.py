from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from news_ingestion.config import Settings
from news_ingestion.models import RawClaim


class ClimateFeverClient:
    def __init__(
        self,
        dataset_name: str,
        split: str,
        max_records: int,
        hf_token: str | None = None,
    ) -> None:
        self.dataset_name = dataset_name
        self.split = split
        self.max_records = max_records
        self.hf_token = hf_token

    @classmethod
    def from_settings(cls, settings: Settings) -> ClimateFeverClient:
        return cls(
            dataset_name=settings.climate_fever.dataset_name,
            split=settings.climate_fever.split,
            max_records=settings.climate_fever.max_records,
            hf_token=(
                settings.hf_token.get_secret_value() if settings.hf_token else None
            ),
        )

    def fetch_claims(self) -> list[RawClaim]:
        records = self._load_records()
        claims: list[RawClaim] = []

        for record in records:
            claims.append(self._raw_claim_from_payload(record))
            if len(claims) >= self.max_records:
                break

        return claims

    def _load_records(self) -> Iterable[dict[str, Any]]:
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
        evidence = payload.get("evidences") or payload.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []

        return RawClaim(
            claim_id=self._string_or_none(payload.get("claim_id") or payload.get("id")),
            claim=str(payload.get("claim") or ""),
            label=self._string_or_none(
                payload.get("claim_label") or payload.get("label")
            ),
            evidence=[item for item in evidence if isinstance(item, dict)],
            source_name="Climate-FEVER",
            language="en",
            country=None,
            extracted_from="climate_fever",
            raw_payload=payload,
        )

    def _string_or_none(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
