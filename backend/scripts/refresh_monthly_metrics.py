"""Compatibility entry point for the unified monthly pipeline."""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.refresh_monthly_pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())