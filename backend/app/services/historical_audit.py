from __future__ import annotations

import base64
import calendar
import csv
import json
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import RepoMonthlyAudit
from app.services.monthly_audit import _governance_file_score

SECURITY_WEIGHTS = {
    "scorecard": 0.60,
    "security_policy": 0.10,
    "dependency_update": 0.10,
    "sast": 0.10,
    "workflow_hygiene": 0.10,
}
PINNED_ACTION = re.compile(r"^[0-9a-fA-F]{40}$")
USES_PATTERN = re.compile(r"(?m)^\s*-?\s*uses:\s*['\"]?([^\s'\"]+)")


def month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def month_end_iso(value: date) -> str:
    last_day = calendar.monthrange(value.year, value.month)[1]
    return f"{value.year:04d}-{value.month:02d}-{last_day:02d}T23:59:59Z"


def classify_repository_paths(paths: Iterable[str]) -> dict[str, Any]:
    normalized = sorted({str(path).replace("\\", "/").strip("/") for path in paths if path})
    lowered = {path.casefold(): path for path in normalized}

    def basename_matches(*prefixes: str) -> bool:
        for path in lowered:
            if "/" in path and not path.startswith((".github/", "docs/")):
                continue
            basename = path.rsplit("/", 1)[-1]
            stem = basename.split(".", 1)[0]
            if any(stem == prefix or basename.startswith(prefix + ".") for prefix in prefixes):
                return True
        return False

    files = {
        "readme": basename_matches("readme"),
        "license": basename_matches("license", "licence", "copying"),
        "contributing": basename_matches("contributing"),
        "code_of_conduct": basename_matches("code_of_conduct", "code-of-conduct"),
        "security": basename_matches("security"),
        "governance": basename_matches("governance"),
        "maintainers": basename_matches("maintainers", "owners"),
        "codeowners": any(path.endswith("codeowners") for path in lowered),
        "issue_template": any(path.startswith(".github/issue_template/") for path in lowered),
        "pull_request_template": any(
            path.startswith(".github/pull_request_template")
            or path.startswith("docs/pull_request_template")
            or path.startswith("pull_request_template")
            for path in lowered
        ),
    }
    dependency_update = any(
        path in {
            ".github/dependabot.yml",
            ".github/dependabot.yaml",
            "renovate.json",
            "renovate.json5",
            ".renovaterc",
            ".renovaterc.json",
        }
        for path in lowered
    )
    workflow_paths = [
        original
        for path, original in lowered.items()
        if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
    ]
    return {
        "files": files,
        "dependency_update": dependency_update,
        "workflow_paths": sorted(workflow_paths),
        "paths": normalized,
    }


def analyze_workflows(contents: dict[str, str]) -> dict[str, Any]:
    combined = "\n".join(contents.values()).casefold()
    sast_markers = (
        "github/codeql-action",
        "returntocorp/semgrep-action",
        "semgrep/semgrep-action",
        "snyk/actions",
        "sonarsource/sonarqube-scan-action",
        "aquasecurity/trivy-action",
        "pycqa/bandit",
    )
    sast = any(marker in combined for marker in sast_markers)
    references = []
    for content in contents.values():
        references.extend(USES_PATTERN.findall(content))
    external = [reference for reference in references if not reference.startswith("./") and "@" in reference]
    pinned = [reference for reference in external if PINNED_ACTION.fullmatch(reference.rsplit("@", 1)[-1])]
    hygiene = 100.0 * len(pinned) / len(external) if external else None
    return {
        "sast": sast,
        "workflow_hygiene_score": hygiene,
        "action_references": len(external),
        "pinned_action_references": len(pinned),
    }


class GitHubHistoricalEvidence:
    def __init__(self, timeout: float = 30.0, retries: int = 3) -> None:
        self.retries = retries
        self.client = httpx.Client(timeout=timeout, verify=False, trust_env=False)
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "OpenSage-historical-audit/1.0",
        }
        if settings.GITHUB_TOKEN:
            self.headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"

    def close(self) -> None:
        self.client.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"https://api.github.com{path}"
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = self.client.get(url, headers=self.headers, params=params)
                if response.status_code == 404:
                    return None
                if response.status_code != 429 and response.status_code < 500:
                    response.raise_for_status()
                    return response.json()
                response.raise_for_status()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt + 1 < self.retries:
                    time.sleep(0.6 * (2 ** attempt))
        raise RuntimeError(f"GitHub history request failed for {path}: {last_error}")

    def _tree(self, repo: str, tree_sha: str, recursive: bool = False) -> list[dict[str, Any]]:
        params = {"recursive": "1"} if recursive else None
        payload = self._get(f"/repos/{repo}/git/trees/{tree_sha}", params=params) or {}
        return payload.get("tree") or []

    def _blob_text(self, repo: str, sha: str) -> str:
        payload = self._get(f"/repos/{repo}/git/blobs/{sha}") or {}
        content = payload.get("content")
        if not isinstance(content, str):
            return ""
        try:
            return base64.b64decode(content).decode("utf-8", errors="ignore")
        except (ValueError, TypeError):
            return ""

    def fetch(self, repo: str, metric_month: date) -> dict[str, Any]:
        metadata = self._get(f"/repos/{repo}")
        if not isinstance(metadata, dict):
            raise ValueError(f"repository not found: {repo}")
        default_branch = metadata.get("default_branch") or "main"
        commits = self._get(
            f"/repos/{repo}/commits",
            params={"sha": default_branch, "until": month_end_iso(metric_month), "per_page": 1},
        )
        if not isinstance(commits, list) or not commits:
            raise ValueError(f"no commit at or before {month_end_iso(metric_month)} for {repo}")
        commit = commits[0]
        commit_sha = commit.get("sha")
        tree_sha = (((commit.get("commit") or {}).get("tree") or {}).get("sha"))
        if not commit_sha or not tree_sha:
            raise ValueError(f"commit tree unavailable for {repo}")

        root_entries = self._tree(repo, tree_sha)
        paths: list[str] = []
        workflow_blobs: dict[str, str] = {}
        for entry in root_entries:
            entry_path = entry.get("path")
            if entry_path:
                paths.append(entry_path)
            if entry.get("type") != "tree" or entry_path not in {".github", "docs"}:
                continue
            subtree = self._tree(repo, entry.get("sha"), recursive=entry_path == ".github")
            for child in subtree:
                child_path = f"{entry_path}/{child.get('path')}"
                paths.append(child_path)
                lowered = child_path.casefold()
                if (
                    child.get("type") == "blob"
                    and lowered.startswith(".github/workflows/")
                    and lowered.endswith((".yml", ".yaml"))
                ):
                    workflow_blobs[child_path] = self._blob_text(repo, child.get("sha"))

        classified = classify_repository_paths(paths)
        workflow = analyze_workflows(workflow_blobs)
        return {
            "repo": repo,
            "metric_month": month_start(metric_month).isoformat(),
            "commit_sha": commit_sha,
            "commit_date": (((commit.get("commit") or {}).get("committer") or {}).get("date")),
            "default_branch": default_branch,
            "files": classified["files"],
            "dependency_update": classified["dependency_update"],
            "workflow_paths": classified["workflow_paths"],
            **workflow,
        }


def _normalize_scorecard_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not record or record.get("score") is None:
        return None
    numeric_score = float(record["score"])
    normalized_score = numeric_score * 10.0 if numeric_score <= 10.0 else numeric_score
    checks = record.get("checks") or record.get("checks_json") or {}
    if isinstance(checks, str):
        try:
            checks = json.loads(checks)
        except ValueError:
            checks = {}
    return {
        "repo": str(record.get("repo") or record.get("repo_name") or "").removeprefix("github.com/"),
        "date": str(record.get("date") or record.get("scorecard_date") or "")[:10],
        "score": max(0.0, min(100.0, normalized_score)),
        "checks": checks,
    }


def load_scorecard_export(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    source = Path(path)
    if source.suffix.casefold() == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            records = list(csv.DictReader(handle))
    else:
        raw_text = source.read_text(encoding="utf-8")
        if source.suffix.casefold() == ".json":
            payload = json.loads(raw_text)
            records = payload if isinstance(payload, list) else payload.get("records", [])
        else:
            records = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in records:
        normalized = _normalize_scorecard_record(raw)
        if normalized and normalized["repo"]:
            grouped.setdefault(normalized["repo"], []).append(normalized)
    for values in grouped.values():
        values.sort(key=lambda item: item["date"])
    return grouped


def query_scorecard_bigquery(repos: list[str], metric_month: date, project_id: str) -> dict[str, list[dict[str, Any]]]:
    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise RuntimeError("google-cloud-bigquery is required for --bigquery-project") from exc

    month = month_start(metric_month)
    next_month = date(month.year + (1 if month.month == 12 else 0), 1 if month.month == 12 else month.month + 1, 1)
    names = [f"github.com/{repo}" for repo in repos]
    sql = """
        SELECT repo.name AS repo, CAST(date AS STRING) AS date, score,
               TO_JSON_STRING(checks) AS checks_json
        FROM `openssf.scorecardcron.scorecard-v2`
        WHERE repo.name IN UNNEST(@repos)
          AND DATE(date) >= @start_date
          AND DATE(date) < @end_date
        QUALIFY ROW_NUMBER() OVER (PARTITION BY repo.name ORDER BY date DESC) = 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("repos", "STRING", names),
            bigquery.ScalarQueryParameter("start_date", "DATE", month),
            bigquery.ScalarQueryParameter("end_date", "DATE", next_month),
        ]
    )
    client = bigquery.Client(project=project_id)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in client.query(sql, job_config=job_config).result():
        normalized = _normalize_scorecard_record(dict(row))
        if normalized:
            grouped.setdefault(normalized["repo"], []).append(normalized)
    return grouped


def scorecard_for_month(grouped: dict[str, list[dict[str, Any]]], repo: str, metric_month: date) -> dict[str, Any] | None:
    prefix = f"{metric_month.year:04d}-{metric_month.month:02d}-"
    matches = [record for record in grouped.get(repo, []) if record.get("date", "").startswith(prefix)]
    return matches[-1] if matches else None


def collect_historical_monthly_audit(
    db: Session,
    repo: str,
    metric_month: date,
    scorecard_record: dict[str, Any] | None = None,
) -> RepoMonthlyAudit:
    month = month_start(metric_month)
    github = GitHubHistoricalEvidence()
    try:
        evidence = github.fetch(repo, month)
    finally:
        github.close()

    files = evidence["files"]
    governance_score = _governance_file_score(files)
    governance_completeness = 1.0
    scorecard = _normalize_scorecard_record(scorecard_record)
    components: dict[str, float | None] = {
        "scorecard": scorecard["score"] if scorecard else None,
        "security_policy": 100.0 if files.get("security") else 0.0,
        "dependency_update": 100.0 if evidence.get("dependency_update") else 0.0,
        "sast": 100.0 if evidence.get("sast") else 0.0,
        "workflow_hygiene": evidence.get("workflow_hygiene_score"),
    }
    available_weight = sum(SECURITY_WEIGHTS[key] for key, value in components.items() if value is not None)
    security_score = None
    if available_weight >= 0.80:
        security_score = sum(
            float(value) * SECURITY_WEIGHTS[key]
            for key, value in components.items()
            if value is not None
        ) / available_weight

    observed_at = datetime.now(timezone.utc)
    security_completeness = available_weight
    completeness = (governance_completeness + security_completeness) / 2.0
    errors = [] if scorecard else ["no OpenSSF Scorecard scan for target month"]
    status = "complete" if security_score is not None and completeness >= 0.90 else "partial"
    payload = {
        "repo": repo,
        "metric_month": month,
        "governance_score": governance_score,
        "security_score": security_score,
        "completeness": completeness,
        "governance_evidence": {
            **evidence,
            "completeness": governance_completeness,
            "evidence_kind": "git_month_end_tree",
        },
        "security_evidence": {
            "scorecard": scorecard,
            "components": components,
            "completeness": security_completeness,
            "commit_sha": evidence["commit_sha"],
            "workflow_paths": evidence["workflow_paths"],
            "action_references": evidence["action_references"],
            "pinned_action_references": evidence["pinned_action_references"],
            "evidence_kind": "git_month_end_tree+openssf_monthly_scan",
        },
        "status": status,
        "source": "git_history+openssf_bigquery" if scorecard else "git_history",
        "observed_at": observed_at,
        "error": "; ".join(errors) or None,
    }
    statement = insert(RepoMonthlyAudit).values(**payload)
    statement = statement.on_conflict_do_update(
        constraint="uq_repo_monthly_audit",
        set_={key: value for key, value in payload.items() if key not in {"repo", "metric_month"}},
    ).returning(RepoMonthlyAudit.id)
    audit_id = db.execute(statement).scalar_one()
    db.commit()
    return db.get(RepoMonthlyAudit, audit_id)