from __future__ import annotations

import sys

from news_ingestion.pipeline import transform_live_run
from news_ingestion.script_utils import configure_logging


def main() -> int:
    configure_logging()
    transform_live_run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
