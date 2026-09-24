"""DataForGood client for fetching raw claim records."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from news_ingestion.config import Settings
from news_ingestion.models import RawClaim
from news_ingestion.text import coerce_nonempty_string


class DataForGoodClient:
    """Fetch claims from the DataForGood climate misinformation dataset."""

    def __init__(
        self,
        dataset_name: str,
        splits: list[str],
        max_records: int,
        hf_token: str | None = None,
    ) -> None:
        """Initialize a DataForGood client with dataset settings."""
        self.dataset_name = dataset_name
        self.splits = splits
        self.max_records = max_records
        self.hf_token = hf_token

    @classmethod
    def from_settings(cls, settings: Settings) -> DataForGoodClient:
        """Create a DataForGood client from application settings."""
        return cls(
            dataset_name=settings.dataforgood.dataset_name,
            splits=settings.dataforgood.splits,
            max_records=settings.dataforgood.max_records,
            hf_token=(
                settings.hf_token.get_secret_value() if settings.hf_token else None
            ),
        )

    def fetch_claims(self) -> list[RawClaim]:
        """Fetch and normalize DataForGood claims."""
        claims: list[RawClaim] = []

        for record in self._iter_dataset_records():
            claims.append(self._raw_claim_from_payload(record))
            if len(claims) >= self.max_records:
                break

        return claims

    def _iter_dataset_records(self) -> Iterable[dict[str, Any]]:
        """Iterate records from all configured Hugging Face dataset splits."""
        from datasets import load_dataset

        for split in self.splits:
            try:
                dataset = load_dataset(
                    self.dataset_name, split=split, token=self.hf_token
                )
            except Exception as exc:
                msg = f"Could not load DataForGood dataset split '{split}'."
                raise RuntimeError(msg) from exc
            for record in dataset:
                payload = dict(record)
                payload["split"] = split
                yield payload

    def _raw_claim_from_payload(self, payload: dict[str, Any]) -> RawClaim:
        """Convert a DataForGood payload into a raw claim."""
        return RawClaim(
            claim_id=coerce_nonempty_string(payload.get("task_id")),
            claim=self._extract_messages_text(payload.get("messages")),
            label=coerce_nonempty_string(payload.get("label")),
            evidence=[],
            source_name=coerce_nonempty_string(payload.get("channel")),
            language="fr",
            country=coerce_nonempty_string(payload.get("country")),
            extracted_from="dataforgood_climate_misinformation_rcot",
            raw_payload=payload,
        )

    def _extract_messages_text(self, messages: object) -> str:
        """Extract claim text from list or JSON-encoded message payloads."""
        if isinstance(messages, str):
            try:
                messages = json.loads(messages)
            except json.JSONDecodeError:
                return messages.strip()

        if isinstance(messages, list):
            return "\n".join(
                self._message_content(message) for message in messages
            ).strip()

        return ""

    def _message_content(self, message: object) -> str:
        """Extract text content from a single message payload."""
        if isinstance(message, dict):
            content = message.get("content") or message.get("text") or ""
            return str(content).strip()
        return str(message).strip()
