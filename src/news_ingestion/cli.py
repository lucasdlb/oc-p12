"""Command-line interface for ingestion workflows."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from news_ingestion.composition import (
    extract_climate_fever_to_json,
    extract_dataforgood_to_json,
    extract_fakeddit_to_json,
    extract_gdelt_to_json,
    extract_live_sources,
    extract_newsdata_to_json,
    extract_rss_to_json,
    extract_static_sources,
    transform_live_run,
    transform_static_sources,
)
from news_ingestion.config import get_settings
from news_ingestion.logging_config import configure_logging
from news_ingestion.paths import project_paths

SOURCE_NAMES = (
    "newsdata",
    "gdelt",
    "rss",
    "fakeddit",
    "climate-fever",
    "dataforgood",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(prog="news-ingestion")
    commands = parser.add_subparsers(dest="command", required=True)

    extract_parser = commands.add_parser("extract", help="Extract source records")
    extract_target = extract_parser.add_mutually_exclusive_group(required=True)
    extract_target.add_argument("--source", choices=SOURCE_NAMES)
    extract_target.add_argument("--group", choices=("live", "static"))
    extract_parser.add_argument("--run-id")

    transform_parser = commands.add_parser(
        "transform", help="Transform existing raw artifacts"
    )
    transform_parser.add_argument("--group", choices=("live", "static"), required=True)
    transform_parser.add_argument("--run-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected ingestion command."""
    configure_logging()
    arguments = build_parser().parse_args(argv)
    settings = get_settings()

    if arguments.command == "extract":
        _run_extraction(arguments.source, arguments.group, arguments.run_id, settings)
    else:
        _run_transformation(arguments.group, arguments.run_id, settings)
    return 0


def _run_extraction(source: str | None, group: str | None, run_id, settings) -> None:
    """Run one source or source-group extraction."""
    if group == "live":
        extract_live_sources(run_id, settings)
        return
    if group == "static":
        extract_static_sources(settings)
        return
    if source == "newsdata":
        extract_newsdata_to_json(run_id, settings)
    elif source == "gdelt":
        extract_gdelt_to_json(run_id, settings)
    elif source == "rss":
        extract_rss_to_json(run_id, settings)
    elif source == "fakeddit":
        extract_fakeddit_to_json(settings)
    elif source == "climate-fever":
        extract_climate_fever_to_json(settings)
    elif source == "dataforgood":
        extract_dataforgood_to_json(settings)
    else:
        msg = "An extraction source or group is required."
        raise ValueError(msg)


def _run_transformation(group: str, run_id, settings) -> None:
    """Transform artifacts discovered at the explicit CLI boundary."""
    paths = project_paths(settings)
    if group == "live":
        input_paths = sorted(paths.live_raw_dir(run_id).glob("*.json"))
        transform_live_run(input_paths, run_id, settings)
        return
    input_paths = sorted(paths.static_raw_dir().glob("*.json"))
    transform_static_sources(input_paths, settings)


if __name__ == "__main__":
    raise SystemExit(main())
