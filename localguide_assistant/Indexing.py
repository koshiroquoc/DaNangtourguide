"""Backward-compatible wrapper for the new indexing command."""

import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from localguide_assistant.indexer import main


if __name__ == "__main__":
    raise SystemExit(main())
