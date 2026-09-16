from __future__ import annotations

import sys

from news_ingestion.pipeline import fetch_live_sources
from news_ingestion.script_utils import configure_logging


def main() -> int:
    configure_logging()
    fetch_live_sources()
    return 0


if __name__ == "__main__":
    sys.exit(main())
