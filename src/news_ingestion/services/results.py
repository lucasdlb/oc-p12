"""Result contracts shared across application workflows."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceExtractionResult:
    """Metadata for a successfully committed source artifact."""

    source: str
    artifact_path: Path
    record_count: int
    duration_ms: int


@dataclass(frozen=True)
class SourceExtractionFailure:
    """Metadata for a failed source extraction attempt."""

    source: str
    duration_ms: int
    error_type: str
    error_message: str


@dataclass(frozen=True)
class ExtractionBatchResult:
    """Successful artifacts and failures from a source group extraction."""

    successful: tuple[SourceExtractionResult, ...]
    failures: tuple[SourceExtractionFailure, ...]

    @property
    def artifact_paths(self) -> tuple[Path, ...]:
        """Return artifacts committed during this extraction attempt."""
        return tuple(result.artifact_path for result in self.successful)

    @property
    def record_count(self) -> int:
        """Return the total number of extracted records."""
        return sum(result.record_count for result in self.successful)

    def to_serializable_dict(self) -> dict[str, object]:
        """Return JSON-serializable metadata for workflow boundaries."""
        return {
            "artifact_paths": [str(path) for path in self.artifact_paths],
            "record_count": self.record_count,
            "successful_sources": [result.source for result in self.successful],
            "failed_sources": [failure.source for failure in self.failures],
        }


@dataclass(frozen=True)
class TransformResult:
    """Metadata for a committed processed-record artifact."""

    artifact_path: Path
    record_count: int
    duration_ms: int
