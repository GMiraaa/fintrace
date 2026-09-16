from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.api.dependencies import build_pipeline
from src.config import AppSettings
from src.logging_config import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process corporate action PDF notices with FinTrace."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="PDFs to process; defaults to every PDF in INPUT_DIR.",
    )
    args = parser.parse_args()

    settings = AppSettings.from_env()
    configure_logging(settings.log_level)
    paths = args.paths or sorted(settings.input_dir.glob("*.pdf"))
    if not paths:
        parser.error("no PDF documents were found")

    result = build_pipeline(settings).process_batch(paths)
    print(json.dumps(result.report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 1 if result.report.summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
