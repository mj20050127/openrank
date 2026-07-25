from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.base import SessionLocal
from app.services.bootstrap_snapshot import (
    DEFAULT_SNAPSHOT_PATH,
    SNAPSHOT_TABLES,
)


def _repositories(path: Path) -> list[str]:
    repositories = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not repositories:
        raise ValueError(f"no repositories listed in {path}")
    return repositories


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _trim_snapshot_row(table: str, row: dict[str, Any]) -> dict[str, Any]:
    if table == "repo_docs":
        limits = {
            "content": 20_000,
            "readme_text": 20_000,
            "contributing_text": 20_000,
            "pr_template_text": 10_000,
        }
        for key, limit in limits.items():
            if isinstance(row.get(key), str):
                row[key] = row[key][:limit]
    elif table == "repo_issues":
        if isinstance(row.get("body"), str):
            row["body"] = row["body"][:4_000]
        row["raw"] = None
    elif table == "current_repo_assessments":
        evidence = row.get("evidence_json")
        if isinstance(evidence, dict):
            governance = evidence.get("governance")
            if isinstance(governance, dict):
                # Full repository path listings dominate the snapshot size, while
                # the UI only needs the derived file/workflow evidence.
                governance["paths"] = []
                governance["workflow_paths"] = []
    return row


def _is_valid_snapshot_row(table: str, row: dict[str, Any]) -> bool:
    if table != "repo_issues":
        return True
    return bool(
        row.get("issue_number") is not None
        and row.get("url")
        and row.get("title")
        and row.get("updated_at")
        and row.get("category") in {"good_first", "help_wanted", "docs", "i18n"}
        and not row.get("is_pull_request")
    )


def export_snapshot(repositories: list[str], output: Path) -> dict[str, Any]:
    tables: dict[str, list[dict[str, Any]]] = {}
    with SessionLocal() as db:
        for table_name, specification in SNAPSHOT_TABLES.items():
            model = specification.model
            repository_column = getattr(model, specification.repository_column)
            records = db.execute(
                select(model)
                .where(repository_column.in_(repositories))
                .order_by(repository_column)
            ).scalars()
            rows = []
            for record in records:
                row = {
                    column.name: _json_value(getattr(record, column.name))
                    for column in model.__table__.columns
                    if column.name not in specification.excluded_columns
                }
                row = _trim_snapshot_row(table_name, row)
                if _is_valid_snapshot_row(table_name, row):
                    rows.append(row)
            tables[table_name] = rows

    missing_catalog = sorted(
        set(repositories)
        - {row["repo_full_name"] for row in tables["repo_catalog"]}
    )
    missing_history = sorted(
        set(repositories)
        - {row["repo"] for row in tables["metric_points"]}
    )
    if missing_catalog or missing_history:
        raise RuntimeError(
            "snapshot source is incomplete; "
            f"missing catalog={missing_catalog}, missing history={missing_history}"
        )

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "OpenDigger + GitHub API + OpenSSF Scorecard",
        "repositories": repositories,
        "tables": tables,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the curated OpenSage grading snapshot"
    )
    parser.add_argument(
        "--repos-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "repos.txt",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    args = parser.parse_args()

    repositories = _repositories(args.repos_file)
    payload = export_snapshot(repositories, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "repositories": len(payload["repositories"]),
                "rows": {
                    key: len(value)
                    for key, value in payload["tables"].items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
