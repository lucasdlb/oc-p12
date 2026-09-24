"""Centralized path construction for pipeline inputs and outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


def sanitize_run_id(run_id: str) -> str:
    """Normalize a run ID for safe filesystem use."""
    cleaned_run_id = re.sub(r"[^A-Za-z0-9_.=-]+", "_", run_id.strip())
    cleaned_run_id = cleaned_run_id.strip("_")
    if cleaned_run_id in {"", ".", ".."}:
        return "manual"
    return cleaned_run_id


@dataclass(frozen=True)
class ProjectPaths:
    """Build project data and metrics paths from configured root directories."""

    raw_root: Path
    processed_root: Path
    metrics_root: Path

    def live_raw_dir(self, run_id: str | None = None) -> Path:
        """Return the raw data directory for live source outputs."""
        base_dir = self.raw_root / "live"
        if run_id:
            return base_dir / "runs" / sanitize_run_id(run_id)
        return base_dir

    def static_raw_dir(self) -> Path:
        """Return the raw data directory for static source outputs."""
        return self.raw_root / "static"

    def processed_output_path(self, run_id: str | None = None) -> Path:
        """Return the processed records path for a live run."""
        if run_id:
            return (
                self.processed_root
                / "runs"
                / sanitize_run_id(run_id)
                / "processed_records.json"
            )
        return self.processed_root / "processed_records.json"

    def static_processed_output_path(self) -> Path:
        """Return the processed records path for static source data."""
        return self.processed_root / "static" / "processed_records.json"

    def metrics_output_path(self, run_id: str | None = None) -> Path:
        """Return the metrics path for a run or manual execution."""
        if run_id:
            return self.metrics_root / "runs" / sanitize_run_id(run_id) / "metrics.json"
        return self.metrics_root / "metrics.json"


class PathSettings(Protocol):
    raw_data_dir: Path
    processed_data_dir: Path
    metrics_data_dir: Path


def project_paths(settings: PathSettings) -> ProjectPaths:
    """Create project paths from an object with configured data directories."""
    return ProjectPaths(
        raw_root=settings.raw_data_dir,
        processed_root=settings.processed_data_dir,
        metrics_root=settings.metrics_data_dir,
    )
