"""Backward-compatible entry point for the Streamlit application."""

import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from localguide_assistant.app import main


main()
