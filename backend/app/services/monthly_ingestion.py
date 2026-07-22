from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from datetime import date, datetime, timezone
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.models import IngestionJob, MetricPoint, RepositoryDataStatus, RepositoryMetricStatus
from app.models import RepoCatalog
from app.registry import MONTHLY_METRIC_FILES
from app.services.current_health import collect_current_assessment
from app.services.monthly_audit import collect_monthly_audit
from app.services.monthly_scoring import recompute_monthly_assessments
from app.tools.github_client import GitHubClient

REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
COUNT_LIST_METRICS = {"contributors", "new_contributors", "inactive_contributors", "participants"}
OPENDIGGER_BASE = "https://oss.open-digger.cn/github"


def normalize_repo(value: str) -> str:
    repo = (value or "").strip().removeprefix("https://github.com/").strip("/")
    if not REPO_PATTERN.fullmatch(repo):
        raise ValueError("repository must use owner/repo format")
    return repo


def normalize_monthly_payload(metric: str, payload: Any) -> dict[date, float]:
    if not isinstance(payload, dict):
        return {}
    target = payload
    if isinstance(payload.get("avg"), dict):
        target = payload["avg"]
    elif isinstance(payload.get("sum"), dict):
        target = payload["sum"]
    records: dict[date, float] = {}
    for key, raw_value in target.items():
        if not isinstance(key, str) or not re.fullmatch(r"\d{4}-\d{2}", key):
            continue
        value: float | None = None
        if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
            value = float(raw_value)
        elif metric in COUNT_LIST_METRICS and isinstance(raw_value, list):
            value = float(len(raw_value))
        if value is not None and value == value:
            year, month = key.split("-")
            records[date(int(year), int(month), 1)] = value
    return records


class OpenDiggerMonthlyIngestion:
    def __init__(self, timeout: float = 30.0, retries: int = 3) -> None:
        self.retries = retries
        self.client = httpx.Client(timeout=timeout, follow_redirects=True, verify=False, trust_env=False)

    def close(self) -> None:
        self.client.close()

    def _get(self, url: str) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = self.client.get(url, headers={"User-Agent": "OpenSage-monthly-ingestion/1.0"})
                if response.status_code == 404:
                    return response
                response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt + 1 < self.retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"OpenDigger request failed: {last_error}")

    def is_supported(self, repo: str) -> bool:
        return self._get(f"{OPENDIGGER_BASE}/{repo}/meta.json").status_code != 404

    def fetch_metric(self, repo: str, metric: str, filename: str) -> tuple[dict[date, float], str | None]:
        response = self._get(f"{OPENDIGGER_BASE}/{repo}/{filename}")
        if response.status_code == 404:
            return {}, "not_available"
        try:
            return normalize_monthly_payload(metric, response.json()), None
        except ValueError as exc:
            return {}, f"invalid_json: {exc}"


def _upsert_catalog(db: Session, repo: str, github: dict[str, Any]) -> RepoCatalog:
    canonical = github.get("full_name") or repo
    row = db.get(RepoCatalog, canonical) or RepoCatalog(repo_full_name=canonical)
    license_info = github.get("license") or {}
    row.description = github.get("description")
    row.homepage = github.get("homepage")
    row.primary_language = github.get("language")
    row.topics = github.get("topics") or []
    row.tags = github.get("topics") or []
    row.stacks = [github.get("language")] if github.get("language") else []
    row.domains = row.domains or []
    row.default_branch = github.get("default_branch")
    row.license = license_info.get("spdx_id") or license_info.get("key")
    row.stars = github.get("stargazers_count")
    row.forks = github.get("forks_count")
    row.open_issues_count = github.get("open_issues_count")
    pushed_at = github.get("pushed_at")
    row.pushed_at = datetime.fromisoformat(pushed_at.replace("Z", "+00:00")) if pushed_at else None
    db.add(row)
    db.commit()
    return row


def _status_row(db: Session, repo: str, scope: str = "user") -> RepositoryDataStatus:
    row = db.get(RepositoryDataStatus, repo)
    if row is None:
        row = RepositoryDataStatus(repo=repo, scope=scope, enabled=True, sync_status="pending")
        db.add(row)
        db.flush()
    return row


def _record_metric_status(
    db: Session,
    repo: str,
    metric: str,
    filename: str,
    records: dict[date, float],
    source_status: str,
    error: str | None = None,
) -> dict[str, Any]:
    row = db.execute(
        select(RepositoryMetricStatus).where(
            RepositoryMetricStatus.repo == repo,
            RepositoryMetricStatus.metric == metric,
        )
    ).scalar_one_or_none()
    if row is None:
        row = RepositoryMetricStatus(repo=repo, metric=metric, filename=filename)

    source_keys = set(records)
    database_keys = set(
        db.execute(
            select(MetricPoint.dt).where(MetricPoint.repo == repo, MetricPoint.metric == metric)
        ).scalars()
    )
    missing = sorted(source_keys - database_keys)
    extra = sorted(database_keys - source_keys)
    digest_payload = [(value.isoformat(), records[value]) for value in sorted(source_keys)]
    row.filename = filename
    row.source_status = source_status
    row.first_month = min(source_keys) if source_keys else None
    row.latest_month = max(source_keys) if source_keys else None
    row.source_key_count = len(source_keys)
    row.database_key_count = len(database_keys)
    row.missing_keys = [value.isoformat() for value in missing]
    row.extra_keys = [value.isoformat() for value in extra]
    row.source_digest = hashlib.sha256(
        json.dumps(digest_payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest() if source_keys else None
    row.last_error = error
    row.last_synced_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    return {
        "status": source_status,
        "filename": filename,
        "source_keys": len(source_keys),
        "database_keys": len(database_keys),
        "missing_keys": row.missing_keys,
        "extra_keys": row.extra_keys,
        "first_month": row.first_month.isoformat() if row.first_month else None,
        "latest_month": row.latest_month.isoformat() if row.latest_month else None,
        "error": error,
    }


def _refresh_coverage(db: Session, status: RepositoryDataStatus) -> None:
    first_month, latest_month, month_count = db.execute(
        select(
            func.min(MetricPoint.dt),
            func.max(MetricPoint.dt),
            func.count(func.distinct(MetricPoint.dt)),
        ).where(
            MetricPoint.repo == status.repo,
            MetricPoint.metric.in_(list(MONTHLY_METRIC_FILES)),
        )
    ).one()
    metric_rows = list(
        db.execute(
            select(RepositoryMetricStatus).where(RepositoryMetricStatus.repo == status.repo)
        ).scalars()
    )
    complete = sum(
        1
        for item in metric_rows
        if item.source_status == "available"
        and not (item.missing_keys or [])
        and not (item.extra_keys or [])
    )
    status.first_month = first_month
    status.latest_month = latest_month
    status.metric_count = sum(1 for item in metric_rows if item.source_status == "available")
    status.month_count = int(month_count or 0)
    status.coverage_ratio = complete / len(MONTHLY_METRIC_FILES) if metric_rows else 0.0


def _update_job(db: Session, job: IngestionJob, **values: Any) -> None:
    for key, value in values.items():
        setattr(job, key, value)
    db.commit()


def create_import_job(db: Session, repo: str, requested_by: str = "user", job_type: str = "full_backfill") -> IngestionJob:
    normalized = normalize_repo(repo)
    existing = db.execute(select(IngestionJob).where(IngestionJob.repo == normalized, IngestionJob.status.in_(["queued", "running"])).order_by(IngestionJob.created_at.desc())).scalars().first()
    if existing:
        return existing
    job = IngestionJob(id=str(uuid.uuid4()), repo=normalized, job_type=job_type, status="queued", stage="queued", progress=0.0, requested_by=requested_by)
    db.add(job)
    _status_row(db, normalized, "user")
    db.commit()
    return job


def run_import_job(job_id: str, include_audit: bool = True) -> None:
    with SessionLocal() as db:
        job = db.get(IngestionJob, job_id)
        if job is None or job.status == "succeeded":
            return
        _update_job(db, job, status="running", stage="validating", progress=0.02, attempts=(job.attempts or 0) + 1, started_at=datetime.now(timezone.utc), error=None)
        ingestion = OpenDiggerMonthlyIngestion()
        try:
            github_data = GitHubClient().get_repo(job.repo)
            if not github_data:
                raise ValueError(f"GitHub repository not found or unavailable: {job.repo}")
            canonical = github_data.get("full_name") or job.repo
            if canonical != job.repo:
                job.repo = canonical
            _upsert_catalog(db, canonical, github_data)
            status = _status_row(db, canonical, "user")
            status.metadata_json = {"archived": bool(github_data.get("archived")), "fork": bool(github_data.get("fork")), "visibility": github_data.get("visibility"), "html_url": github_data.get("html_url")}
            status.sync_status = "checking_opendigger"
            db.commit()

            supported = ingestion.is_supported(canonical)
            status.opendigger_supported = supported
            if not supported:
                status.sync_status = "partial"
                status.last_error = "OpenDigger does not export this repository"
                if include_audit:
                    collect_monthly_audit(db, canonical)
                _update_job(db, job, status="succeeded", stage="degraded_ready", progress=1.0, result_json={"repo": canonical, "opendigger_supported": False, "mode": "degraded"}, finished_at=datetime.now(timezone.utc))
                return

            status.sync_status = "syncing"
            status.last_error = None
            db.commit()
            counts: dict[str, int] = {}
            unavailable: list[str] = []
            metric_results: dict[str, dict[str, Any]] = {}
            total = len(MONTHLY_METRIC_FILES)
            for index, (metric, filename) in enumerate(MONTHLY_METRIC_FILES.items(), start=1):
                _update_job(db, job, stage="fetching_history", current_metric=metric, progress=0.05 + 0.60 * index / total)
                try:
                    records, error = ingestion.fetch_metric(canonical, metric, filename)
                    if error == "not_available":
                        unavailable.append(metric)
                        metric_results[metric] = _record_metric_status(
                            db, canonical, metric, filename, {}, "not_available"
                        )
                        continue
                    if error:
                        metric_results[metric] = _record_metric_status(
                            db, canonical, metric, filename, {}, "failed", error
                        )
                        continue
                    if records:
                        values = [{"repo": canonical, "metric": metric, "dt": metric_month, "value": value, "source": "opendigger", "updated_at": datetime.now(timezone.utc)} for metric_month, value in records.items()]
                        statement = insert(MetricPoint).values(values)
                        statement = statement.on_conflict_do_update(index_elements=["repo", "metric", "dt"], set_={"value": statement.excluded.value, "source": "opendigger", "updated_at": statement.excluded.updated_at})
                        db.execute(statement)
                        db.commit()
                    counts[metric] = len(records)
                    metric_results[metric] = _record_metric_status(
                        db, canonical, metric, filename, records, "available"
                    )
                except Exception as metric_error:
                    db.rollback()
                    metric_results[metric] = _record_metric_status(
                        db, canonical, metric, filename, {}, "failed", str(metric_error)[:2000]
                    )

            _update_job(db, job, stage="verifying_history", current_metric=None, progress=0.70)
            _refresh_coverage(db, status)
            db.commit()
            _update_job(db, job, stage="scoring_history", current_metric=None, progress=0.76)
            assessment_count = recompute_monthly_assessments(db, canonical)
            audit_status = None
            if include_audit:
                _update_job(db, job, stage="monthly_audit", progress=0.90)
                audit = collect_monthly_audit(db, canonical)
                audit_status = audit.status
                assessment_count = recompute_monthly_assessments(db, canonical)

            current_result: dict[str, Any]
            try:
                _update_job(db, job, stage="current_assessment", progress=0.95)
                current = collect_current_assessment(db, canonical)
                current_result = {
                    "status": "ready",
                    "score": current.score_comprehensive,
                    "observed_at": current.observed_at.isoformat(),
                }
            except Exception as current_error:
                db.rollback()
                current_result = {"status": "failed", "error": str(current_error)[:2000]}

            status = _status_row(db, canonical, status.scope)
            _refresh_coverage(db, status)
            status.sync_status = "ready" if status.month_count >= 24 else "partial"
            status.last_full_sync_at = datetime.now(timezone.utc)
            status.last_monthly_sync_at = status.last_full_sync_at
            status.last_error = None if status.sync_status == "ready" else "less than 24 months of exported history"
            db.commit()
            _update_job(db, job, status="succeeded", stage="ready", progress=1.0, current_metric=None, result_json={"repo": canonical, "opendigger_supported": True, "metrics": counts, "metric_verification": metric_results, "unavailable_metrics": unavailable, "assessment_count": assessment_count, "audit_status": audit_status, "current_assessment": current_result}, finished_at=datetime.now(timezone.utc))
        except Exception as exc:
            db.rollback()
            job = db.get(IngestionJob, job_id)
            if job:
                _update_job(db, job, status="failed", stage="failed", error=str(exc)[:2000], finished_at=datetime.now(timezone.utc))
            status = db.get(RepositoryDataStatus, job.repo if job else "") if job else None
            if status:
                status.sync_status = "failed"
                status.last_error = str(exc)[:2000]
                db.commit()
        finally:
            ingestion.close()


def resume_pending_jobs(limit: int = 20) -> int:
    with SessionLocal() as db:
        ids = db.execute(select(IngestionJob.id).where(IngestionJob.status.in_(["queued", "running"])).order_by(IngestionJob.created_at).limit(limit)).scalars().all()
    for job_id in ids:
        run_import_job(job_id)
    return len(ids)