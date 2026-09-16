from __future__ import annotations

from news_ingestion.pipeline import fetch_gdelt
from news_ingestion.script_utils import configure_logging


def main() -> None:
    configure_logging()
    fetch_gdelt()


if __name__ == "__main__":
    main()
