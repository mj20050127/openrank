from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.db.models import MetricPoint
from app.services.bootstrap_snapshot import _coerce_row, _load_payload


def test_snapshot_payload_requires_version_and_repositories():
    snapshot = Path(__file__).with_name(".bootstrap_snapshot_test.json")
    try:
        snapshot.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "repositories": ["example/project"],
                    "tables": {},
                }
            ),
            encoding="utf-8",
        )
        assert _load_payload(snapshot)["repositories"] == ["example/project"]

        snapshot.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "repositories": ["example/project"],
                    "tables": {},
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="unsupported"):
            _load_payload(snapshot)
    finally:
        snapshot.unlink(missing_ok=True)


def test_snapshot_row_coercion_parses_dates_and_drops_generated_ids():
    row = _coerce_row(
        MetricPoint,
        {
            "id": 99,
            "repo": "example/project",
            "metric": "activity",
            "dt": "2026-07-01",
            "value": 42.0,
            "unknown": "ignored",
        },
        ("id",),
    )
    assert row == {
        "repo": "example/project",
        "metric": "activity",
        "dt": date(2026, 7, 1),
        "value": 42.0,
    }
