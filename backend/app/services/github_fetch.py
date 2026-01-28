from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import RepoDoc, RepoIssue
from app.tools.github_client import GitHubClient


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


class GitHubFetchService:
    """Fetch GitHub issues/contents with TTL-backed persistence."""

    LABEL_BUCKETS: Dict[str, Sequence[str]] = {
        "good_first": ["good first issue", "good-first-issue", "good-first"],
        "help_wanted": ["help wanted", "help-wanted"],
        "docs": ["documentation", "docs", "doc"],
        "i18n": ["translation", "i18n", "l10n", "localization"],
    }

    def __init__(
        self,
        db: Session,
        github_client: Optional[GitHubClient] = None,
        issue_ttl_hours: int = 6,
        content_ttl_hours: int = 6,
    ) -> None:
        self.db = db
        self.github = github_client or GitHubClient()
        self.issue_ttl = timedelta(hours=issue_ttl_hours)
        self.content_ttl = timedelta(hours=content_ttl_hours)

    # ---------------- Issues -----------------
    def refresh_repo_issues(self, repo_full_name: str) -> Dict[str, List[RepoIssue]]:
        if hasattr(self.github, "is_rate_limited") and self.github.is_rate_limited():
            return self._group_issues(repo_full_name)

        latest_fetched = self.db.execute(
            select(RepoIssue.fetched_at).where(RepoIssue.repo_full_name == repo_full_name).order_by(RepoIssue.fetched_at.desc()).limit(1)
        ).scalar()
        # use timezone-aware UTC to avoid deprecation warnings
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if latest_fetched and now - latest_fetched < self.issue_ttl:
            return self._group_issues(repo_full_name)

        buckets: Dict[str, List[Dict[str, RepoIssue]]] = {key: [] for key in self.LABEL_BUCKETS}
        seen_keys = set()  # (repo_full_name, issue_number)
        for bucket, labels in self.LABEL_BUCKETS.items():
            for label in labels:
                raw_items = self.github.search_issues(repo_full_name, label, per_page=30)
                if not raw_items:
                    continue
                for item in raw_items:
                    normalized = self._normalize_issue(repo_full_name, item, bucket)
                    if normalized:
                        key = (normalized["repo_full_name"], normalized["issue_number"])
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        buckets[bucket].append(normalized)
                if buckets[bucket]:
                    break  # stop after first label hit per bucket to limit calls

        # upsert
        for bucket, items in buckets.items():
            for item in items:
                self._upsert_issue(item, category=bucket, now=now)
        self.db.commit()

        return self._group_issues(repo_full_name)

    def _upsert_issue(self, item: Dict[str, object], category: str, now: datetime) -> None:
        repo_full_name = item["repo_full_name"]
        issue_number = item["issue_number"]
        github_issue_id = item.get("github_issue_id")

        conflict_target = [RepoIssue.repo_full_name, RepoIssue.github_issue_id] if github_issue_id else [RepoIssue.repo_full_name, RepoIssue.issue_number]
        stmt = (
            insert(RepoIssue)
            .values(
                repo_full_name=repo_full_name,
                issue_number=issue_number,
                url=item.get("url"),
                title=item.get("title"),
                labels=item.get("labels") or [],
                updated_at=item.get("updated_at"),
                category=category,
                difficulty=item.get("difficulty"),
                fetched_at=now,
                github_issue_id=github_issue_id,
                state=item.get("state"),
                is_pull_request=item.get("is_pull_request", False),
                created_at=item.get("created_at"),
            )
            .on_conflict_do_update(
                index_elements=conflict_target,
                set_={
                    "updated_at": insert(RepoIssue).excluded.updated_at,
                    "state": insert(RepoIssue).excluded.state,
                    "labels": insert(RepoIssue).excluded.labels,
                    "difficulty": insert(RepoIssue).excluded.difficulty,
                    "fetched_at": insert(RepoIssue).excluded.fetched_at,
                },
            )
        )
        self.db.execute(stmt)

    def _normalize_issue(self, repo: str, item: Dict[str, object], category: str) -> Optional[Dict[str, object]]:
        if not isinstance(item, dict):
            return None
        number = item.get("number")
        if not number:
            return None
        labels_raw = item.get("labels") or []
        labels = [lbl.get("name") for lbl in labels_raw if isinstance(lbl, dict) and lbl.get("name")]
        title = item.get("title") or ""
        updated_at = _parse_dt(item.get("updated_at"))
        created_at = _parse_dt(item.get("created_at"))
        difficulty = self._classify_issue(labels, title)
        return {
            "repo_full_name": repo,
            "issue_number": number,
            "github_issue_id": item.get("id"),
            "url": item.get("html_url"),
            "title": title,
            "labels": labels,
            "updated_at": updated_at or datetime.now(timezone.utc).replace(tzinfo=None),
            "created_at": created_at,
            "state": item.get("state"),
            "is_pull_request": bool(item.get("pull_request")),
            "difficulty": difficulty,
            "category": category,
        }

    def _classify_issue(self, labels: Sequence[str], title: str) -> str:
        lower_labels = {l.lower() for l in labels if l}
        title_lower = (title or "").lower()
        if any(key in lower_labels for key in ["documentation", "docs", "doc", "translation", "i18n", "l10n", "localization"]):
            return "Easy"
        if "typo" in title_lower or "minor" in title_lower:
            return "Easy"
        if any(key in lower_labels for key in ["bug", "feature", "refactor"]):
            return "Medium"
        return "Medium"

    def _group_issues(self, repo_full_name: str) -> Dict[str, List[RepoIssue]]:
        result: Dict[str, List[RepoIssue]] = {key: [] for key in self.LABEL_BUCKETS}
        rows = self.db.execute(
            select(RepoIssue).where(RepoIssue.repo_full_name == repo_full_name).order_by(RepoIssue.updated_at.desc())
        ).scalars()
        for item in rows:
            bucket = item.category or "help_wanted"
            if bucket in result:
                result[bucket].append(item)
        return result

    # ---------------- Docs -----------------
    def refresh_repo_docs(self, repo_full_name: str) -> RepoDoc:
        existing = self.db.get(RepoDoc, repo_full_name)
        # use timezone-aware UTC
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if existing and existing.fetched_at and now - existing.fetched_at < self.content_ttl:
            return existing

        readme_text = self.github.get_readme(repo_full_name) or None
        contributing_text = self.github.get_content(repo_full_name, "CONTRIBUTING.md") or self.github.get_content(
            repo_full_name, ".github/CONTRIBUTING.md"
        )
        pr_template_text = self.github.get_content(repo_full_name, ".github/PULL_REQUEST_TEMPLATE.md") or None

        extracted = self._extract_commands(readme_text, contributing_text, pr_template_text)
        record = RepoDoc(
            repo_full_name=repo_full_name,
            path="README.md",
            readme_text=readme_text,
            contributing_text=contributing_text,
            pr_template_text=pr_template_text,
            extracted=extracted,
            fetched_at=now,
        )
        self.db.merge(record)
        self.db.commit()
        return record

    def _extract_commands(
        self, readme: Optional[str], contributing: Optional[str], pr_template: Optional[str]
    ) -> Dict[str, List[str]]:
        content = "\n\n".join([part for part in [readme, contributing, pr_template] if part])
        if not content:
            return {}
        commands: List[str] = []
        blocks = []
        lines = content.splitlines()
        block_open = False
        buffer: List[str] = []
        for line in lines:
            if line.strip().startswith("```"):
                if block_open:
                    blocks.append("\n".join(buffer))
                    buffer = []
                block_open = not block_open
                continue
            if block_open:
                buffer.append(line)
        keywords = ["git", "npm", "pnpm", "yarn", "pip", "poetry", "pytest", "make", "go test", "go build"]
        for block in blocks:
            for line in block.splitlines():
                stripped = line.strip()
                lower = stripped.lower()
                if stripped and any(key in lower for key in keywords):
                    commands.append(stripped)
        if not commands:
            for line in lines:
                stripped = line.strip()
                lower = stripped.lower()
                if stripped and any(key in lower for key in keywords):
                    commands.append(stripped)
        deduped = []
        seen = set()
        for c in commands:
            if c in seen:
                continue
            seen.add(c)
            deduped.append(c)
        setup_keywords = ["git clone", "npm install", "pnpm install", "yarn install", "pip install", "poetry install"]
        build_indicators = [
            "npm run",
            "pnpm run",
            "yarn run",
            "npm start",
            "pnpm dev",
            "yarn start",
            "pytest",
            "go test",
            "go build",
            "npm test",
            "make",
        ]
        setup_steps: List[str] = []
        build_steps: List[str] = []
        for cmd in deduped:
            lower = cmd.lower()
            if any(key in lower for key in setup_keywords):
                setup_steps.append(cmd)
            elif any(key in lower for key in build_indicators):
                build_steps.append(cmd)
        return {"setup": setup_steps, "build": build_steps, "commands": deduped}


def freshness_score(updated_at: Optional[datetime]) -> float:
    if not updated_at:
        return 0.6
    days = max((datetime.utcnow() - updated_at).days, 0)
    return float(max(min(math.exp(-days / 30.0), 1.0), 0.0))
