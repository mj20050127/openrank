from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import distinct, func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.db.base import engine
from app.db.models import (
    CurrentRepoAssessment,
    MetricPoint,
    RepoMonthlyAssessment,
    RepoMonthlyAudit,
    RepositoryDataStatus,
    RepositoryMetricStatus,
)
from app.models import RepoCatalog, RepoDoc, RepoIssue

logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "data" / "bootstrap_seed.json"


@dataclass(frozen=True)
class SnapshotTable:
    model: type
    repository_column: str
    excluded_columns: tuple[str, ...] = ()


SNAPSHOT_TABLES: dict[str, SnapshotTable] = {
    "repo_catalog": SnapshotTable(RepoCatalog, "repo_full_name"),
    "repository_data_status": SnapshotTable(RepositoryDataStatus, "repo"),
    "repository_metric_status": SnapshotTable(
        RepositoryMetricStatus, "repo", ("id",)
    ),
    "metric_points": SnapshotTable(MetricPoint, "repo", ("id",)),
    "current_repo_assessments": SnapshotTable(CurrentRepoAssessment, "repo"),
    "repo_monthly_audits": SnapshotTable(RepoMonthlyAudit, "repo", ("id",)),
    "repo_monthly_assessments": SnapshotTable(
        RepoMonthlyAssessment, "repo", ("id",)
    ),
    "repo_docs": SnapshotTable(RepoDoc, "repo_full_name"),
    "repo_issues": SnapshotTable(RepoIssue, "repo_full_name", ("id",)),
}


def snapshot_path() -> Path:
    configured = settings.BOOTSTRAP_SEED_PATH
    return Path(configured).expanduser().resolve() if configured else DEFAULT_SNAPSHOT_PATH


def _parse_temporal(value: Any, column) -> Any:
    if value is None or not isinstance(value, str):
        return value
    try:
        python_type = column.type.python_type
    except (AttributeError, NotImplementedError):
        return value
    if python_type is datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if python_type is date:
        return date.fromisoformat(value)
    return value


def _coerce_row(model: type, raw: dict[str, Any], excluded: tuple[str, ...]) -> dict[str, Any]:
    columns = model.__table__.columns
    allowed = {column.name: column for column in columns if column.name not in excluded}
    return {
        key: _parse_temporal(value, allowed[key])
        for key, value in raw.items()
        if key in allowed
    }


def _batches(rows: list[dict[str, Any]], size: int = 1000):
    for offset in range(0, len(rows), size):
        yield rows[offset : offset + size]


def _load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported bootstrap snapshot schema")
    repositories = payload.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise ValueError("bootstrap snapshot does not list repositories")
    if not isinstance(payload.get("tables"), dict):
        raise ValueError("bootstrap snapshot does not contain tables")
    return payload


def _snapshot_already_present(connection, repositories: list[str]) -> bool:
    expected = len(repositories)
    checks = (
        (
            RepositoryDataStatus,
            RepositoryDataStatus.repo,
            RepositoryDataStatus.scope == "curated",
        ),
        (MetricPoint, MetricPoint.repo, None),
        (CurrentRepoAssessment, CurrentRepoAssessment.repo, None),
        (RepoMonthlyAssessment, RepoMonthlyAssessment.repo, None),
        (RepoDoc, RepoDoc.repo_full_name, None),
    )
    for model, repository_column, extra_condition in checks:
        statement = (
            select(func.count(distinct(repository_column)))
            .select_from(model)
            .where(repository_column.in_(repositories))
        )
        if extra_condition is not None:
            statement = statement.where(extra_condition)
        if int(connection.scalar(statement) or 0) != expected:
            return False
    return True


def import_bootstrap_snapshot(path: Path | None = None) -> dict[str, int]:
    if not settings.BOOTSTRAP_SEED_ENABLED:
        logger.info("Bootstrap snapshot import is disabled")
        return {}

    target = path or snapshot_path()
    if not target.is_file():
        logger.info("Bootstrap snapshot not found at %s; starting without seed data", target)
        return {}

    try:
        payload = _load_payload(target)
        repositories = [str(item) for item in payload["repositories"]]
        imported: dict[str, int] = {}
        with engine.begin() as connection:
            if _snapshot_already_present(connection, repositories):
                logger.info(
                    "Bootstrap snapshot already present for %s repositories",
                    len(repositories),
                )
                return {}
            for name, specification in SNAPSHOT_TABLES.items():
                source_rows = payload["tables"].get(name) or []
                rows = [
                    _coerce_row(
                        specification.model,
                        raw,
                        specification.excluded_columns,
                    )
                    for raw in source_rows
                    if isinstance(raw, dict)
                ]
                affected = 0
                for batch in _batches(rows):
                    if not batch:
                        continue
                    statement = insert(specification.model.__table__).values(batch)
                    result = connection.execute(statement.on_conflict_do_nothing())
                    affected += max(result.rowcount or 0, 0)
                imported[name] = affected

            connection.execute(
                update(RepositoryDataStatus)
                .where(RepositoryDataStatus.repo.in_(repositories))
                .values(scope="curated", enabled=True)
            )

        logger.info(
            "Bootstrap snapshot ready: %s repositories from %s (%s)",
            len(repositories),
            target,
            imported,
        )
        return imported
    except Exception:
        logger.exception("Failed to import bootstrap snapshot from %s", target)
        return {}
