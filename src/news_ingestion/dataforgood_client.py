from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from news_ingestion.config import Settings
from news_ingestion.models import RawClaim


class DataForGoodClient:
    def __init__(
        self,
        dataset_name: str,
        splits: list[str],
        max_records: int,
        hf_token: str | None = None,
    ) -> None:
        self.dataset_name = dataset_name
        self.splits = splits
        self.max_records = max_records
        self.hf_token = hf_token

    @classmethod
    def from_settings(cls, settings: Settings) -> DataForGoodClient:
        return cls(
            dataset_name=settings.dataforgood.dataset_name,
            splits=settings.dataforgood.splits,
            max_records=settings.dataforgood.max_records,
            hf_token=(
                settings.hf_token.get_secret_value() if settings.hf_token else None
            ),
        )

    def fetch_claims(self) -> list[RawClaim]:
        claims: list[RawClaim] = []

        for record in self._load_records():
            claims.append(self._raw_claim_from_payload(record))
            if len(claims) >= self.max_records:
                break

        return claims

    def _load_records(self) -> Iterable[dict[str, Any]]:
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
        return RawClaim(
            claim_id=self._string_or_none(payload.get("task_id")),
            claim=self._extract_messages_text(payload.get("messages")),
            label=self._string_or_none(payload.get("label")),
            evidence=[],
            source_name=self._string_or_none(payload.get("channel")),
            language="fr",
            country=self._string_or_none(payload.get("country")),
            extracted_from="dataforgood_climate_misinformation_rcot",
            raw_payload=payload,
        )

    def _extract_messages_text(self, messages: object) -> str:
        if isinstance(messages, list):
            return "\n".join(
                self._message_content(message) for message in messages
            ).strip()

        if isinstance(messages, str):
            try:
                decoded_messages = json.loads(messages)
            except json.JSONDecodeError:
                return messages.strip()

            if isinstance(decoded_messages, list):
                return "\n".join(
                    self._message_content(message) for message in decoded_messages
                ).strip()

        return ""

    def _message_content(self, message: object) -> str:
        if isinstance(message, dict):
            content = message.get("content") or message.get("text") or ""
            return str(content).strip()
        return str(message).strip()

    def _string_or_none(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
