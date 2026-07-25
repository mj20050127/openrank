from __future__ import annotations

import math
import re
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import MetricPoint, RepositoryDataStatus
from app.models import RepoCatalog, RepoDoc, RepoIssue
from app.services.github_fetch import GitHubFetchService, freshness_score
from app.services.newcomer_scoring import (
    CandidateRepo,
    DocInfo,
    IssueStats,
    RepoMetrics,
    ScoredRepo,
    build_reasons,
    difficulty_label,
    fit_score,
    issue_task_score,
    percentile,
    readiness_score,
)
DOMAIN_ALIASES: Dict[str, tuple[str, ...]] = {
    "frontend": ("frontend",),
    "backend_enterprise": ("backend", "backend-enterprise"),
    "backend": ("backend", "backend-enterprise"),
    "mobile": ("mobile",),
    "cloud_infra": ("cloud", "cloud-observability", "cloud-native"),
    "ai_ml": ("ai", "ai-data", "machine-learning", "deep-learning"),
    "deep_learning": ("deep-learning", "machine-learning", "ai", "ai-data"),
    "time_series": ("time-series", "time-series-forecasting", "timeseries", "ai-data"),
    "databases": ("database", "database-data-infra", "data-infra", "sql"),
    "data_engineering": ("data-engineering", "data-platform", "data-infra"),
    "mlops": ("mlops", "ml-ops", "machine-learning", "ai-data"),
    "visualization": ("visualization", "data-visualization", "oss-analytics", "oss-analytics-education"),
    "developer_tools": ("developer-tools", "developer-tool", "cli", "ide"),
    "security": ("security",),
    "oss_analytics": ("oss-analytics", "oss-analytics-education"),
    "docs": ("docs", "documentation", "docs-i18n-community"),
    "i18n": ("i18n", "internationalization", "localization", "docs-i18n-community"),
}

STACK_ALIASES: Dict[str, tuple[str, ...]] = {
    "javascript": ("javascript", "typescript", "js", "ts"),
    "typescript": ("typescript", "javascript", "ts", "js"),
    "python": ("python",),
    "go": ("go", "golang"),
    "java": ("java",),
    "rust": ("rust",),
    "nodejs": ("nodejs", "node.js", "javascript", "typescript"),
    "react": ("react", "reactjs"),
    "vue": ("vue", "vuejs"),
    "angular": ("angular",),
    "php": ("php", "laravel"),
    "csharp": ("c#", "csharp", ".net", "dotnet"),
    "cpp": ("c", "c++", "cpp"),
    "kotlin": ("kotlin",),
    "swift": ("swift",),
    "flutter": ("dart", "flutter"),
    "sql": ("sql", "database"),
}

class NewcomerPlanService:
    """Recall → Score → Assemble recommendation + issues + timeline."""

    RECALL_LIMIT = 400
    RETURN_LIMIT = 24

    def __init__(self, db: Session, fetcher: Optional[GitHubFetchService] = None) -> None:
        self.db = db
        self.fetcher = fetcher or GitHubFetchService(db)

    # ---------------------------------------------------------
    # Public orchestrations
    # ---------------------------------------------------------
    def build_plan(self, domains: Sequence[str], stacks: Sequence[str], time_per_week: str, keywords: str) -> Dict[str, Any]:
        selected_domains = self._dedupe(domains)
        selected_stacks = self._dedupe(stacks)
        keyword_list = [k.strip().lower() for k in re.split(r"[\s,]+", keywords or "") if k.strip()]
        candidates = self._recall_candidates(selected_domains, selected_stacks, keyword_list)
        if not candidates:
            return {
                "profile": {"domains": selected_domains, "stacks": selected_stacks, "time_per_week": time_per_week, "keywords": keywords},
                "recommended_repos": [],
                "issues_board": {},
                "timeline": [],
                "explain": {},
                "copyable_checklist": "",
            }

        # The map reads persisted cache only. Refreshing hundreds of repositories in
        # a request can exhaust API limits and race with another page request.


        repo_names = [c.repo_full_name for c in candidates]
        metrics_map, resp_p, activity_p = self._load_latest_metrics(repo_names)
        issue_stats_map = self._load_issue_stats(repo_names)
        docs_map = self._load_docs(repo_names)
        supply_p = self._supply_percentiles(issue_stats_map)

        scored = self._score_candidates(
            candidates, keyword_list, selected_domains, selected_stacks, time_per_week,
            metrics_map, issue_stats_map, docs_map, resp_p, activity_p, supply_p
        )

        top_repo = scored[0] if scored else None
        issues_board = self._issues_board(top_repo.repo_full_name if top_repo else None, issue_stats_map, scored)
        timeline = self._build_timeline(top_repo, docs_map.get(top_repo.repo_full_name) if top_repo else None, time_per_week)
        checklist = self._render_checklist(top_repo, timeline)

        return {
            "profile": {
                "domains": selected_domains,
                "stacks": selected_stacks,
                "time_per_week": time_per_week,
                "keywords": keywords,
            },
            "recommended_repos": [
                self._serialize_repo(item, index + 1)
                for index, item in enumerate(scored[: self.RETURN_LIMIT])
            ],
            "issues_board": issues_board,
            "timeline": timeline,
            "explain": {"why": top_repo.reasons if top_repo else []},
            "copyable_checklist": checklist,
        }
    def get_repo_issues(self, repo_full_name: str, readiness: float = 60.0) -> Dict[str, List[Dict[str, Any]]]:
        cached_issue = self.db.execute(
            select(RepoIssue.id).where(RepoIssue.repo_full_name == repo_full_name).limit(1)
        ).scalar()
        repository_status = self.db.get(RepositoryDataStatus, repo_full_name)
        is_curated_snapshot = bool(
            repository_status
            and repository_status.scope == "curated"
            and repository_status.enabled
        )
        if cached_issue is None and not is_curated_snapshot:
            self.fetcher.refresh_repo_issues(repo_full_name)
        issue_stats_map = self._load_issue_stats([repo_full_name])
        scored_repos = [ScoredRepo(repo_full_name=repo_full_name, url=None, fit_score=0, readiness_score=readiness, match_score=readiness, difficulty="", responsiveness=None, activity=None, trend_delta=None, reasons=[], stats=issue_stats_map.get(repo_full_name, IssueStats()))]
        return self._issues_board(repo_full_name, issue_stats_map, scored_repos)

    def build_task_bundle(self, repo_full_name: str, issue_identifier: str | int) -> Dict[str, Any]:
        issues = self.db.execute(
            select(RepoIssue).where(RepoIssue.repo_full_name == repo_full_name)
        ).scalars().all()
        repository_status = self.db.get(RepositoryDataStatus, repo_full_name)
        is_curated_snapshot = bool(
            repository_status
            and repository_status.scope == "curated"
            and repository_status.enabled
        )
        if not issues and not is_curated_snapshot:
            self.fetcher.refresh_repo_issues(repo_full_name)
            issues = self.db.execute(
                select(RepoIssue).where(RepoIssue.repo_full_name == repo_full_name)
            ).scalars().all()
        target = None
        for issue in issues:
            if str(issue.url) == str(issue_identifier) or str(issue.issue_number) == str(issue_identifier) or str(issue.number) == str(issue_identifier):
                target = issue
                break
        if not target and issues:
            target = issues[0]

        docs = self.db.get(RepoDoc, (repo_full_name, "README.md"))
        if docs is None:
            docs = self.fetcher.refresh_repo_docs(repo_full_name)
        steps = self._build_timeline_for_issue(repo_full_name, docs, target)
        checklist = self._render_issue_checklist(repo_full_name, target, steps)
        return {
            "repo_full_name": repo_full_name,
            "issue": {
                "title": target.title if target else None,
                "url": target.url if target else None,
                "number": target.issue_number if target else None,
            },
            "steps": steps,
            "copyable_checklist": checklist,
        }

    # ---------------------------------------------------------
    # Recall & load
    # ---------------------------------------------------------
    def _recall_candidates(self, domains: Sequence[str], stacks: Sequence[str], keywords: List[str]) -> List[CandidateRepo]:
        # Scan the complete curated catalog before applying the user profile.
        rows = self.db.execute(
            select(RepoCatalog)
            .join(RepositoryDataStatus, RepositoryDataStatus.repo == RepoCatalog.repo_full_name)
            .where(RepositoryDataStatus.scope == "curated", RepositoryDataStatus.enabled.is_(True))
            .order_by(RepoCatalog.repo_full_name)
        ).scalars().all()

        def build_candidate(row) -> CandidateRepo:
            domain_values = list(row.domains or [])
            if getattr(row, "seed_domain", None):
                domain_values.append(row.seed_domain)
            if not domain_values:
                domain_values.extend(row.topics or [])
            stack_values = list(row.stacks or [])
            if row.primary_language:
                stack_values.append(row.primary_language)
            stack_values.extend(row.tags or [])
            stack_values.extend(row.topics or [])
            return CandidateRepo(
                repo_full_name=row.repo_full_name,
                url=f"https://github.com/{row.repo_full_name}",
                domains=self._dedupe(domain_values),
                stacks=self._dedupe(stack_values),
                tags=row.tags or [],
                description=row.description or "",
                seed_domain=row.seed_domain,
            )

        def strict_match(candidate: CandidateRepo) -> bool:
            keyword_hit = not keywords or self._keyword_hit(candidate.tags, candidate.description, keywords)
            return self._matches_profile(candidate, domains, stacks, require_all=True) and keyword_hit

        def relaxed_match(candidate: CandidateRepo) -> bool:
            keyword_hit = not keywords or self._keyword_hit(candidate.tags, candidate.description, keywords)
            return self._matches_profile(candidate, domains, stacks, require_all=False) and keyword_hit

        candidates_all = [build_candidate(row) for row in rows]
        strict_results = [candidate for candidate in candidates_all if strict_match(candidate)]
        relaxed_results = strict_results[:]
        for candidate in candidates_all:
            if candidate in relaxed_results:
                continue
            if relaxed_match(candidate):
                relaxed_results.append(candidate)
            if len(relaxed_results) >= self.RECALL_LIMIT:
                break
        return relaxed_results[: self.RECALL_LIMIT]

    @staticmethod
    def _dedupe(values: Sequence[str]) -> List[str]:
        result: List[str] = []
        seen = set()
        for value in values or []:
            cleaned = str(value).strip()
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                result.append(cleaned)
        return result

    @staticmethod
    def _normal_key(value: str) -> str:
        return re.sub(r"[^a-z0-9+#.]+", "", str(value or "").lower())

    def _match_list(self, values: Sequence[str], target: str) -> bool:
        target_key = self._normal_key(target)
        return bool(target_key) and any(self._normal_key(value) == target_key for value in values or [])

    def _matches_selection(
        self,
        candidate_values: Sequence[str],
        selections: Sequence[str],
        aliases: Dict[str, tuple[str, ...]],
    ) -> bool:
        return any(
            any(self._match_list(candidate_values, alias) for alias in aliases.get(selection.lower(), (selection,)))
            for selection in selections or []
        )

    def _matches_profile(
        self,
        candidate: CandidateRepo,
        domains: Sequence[str],
        stacks: Sequence[str],
        require_all: bool,
    ) -> bool:
        active_matches = []
        if domains:
            active_matches.append(self._matches_selection(candidate.domains, domains, DOMAIN_ALIASES))
        if stacks:
            active_matches.append(self._matches_selection(candidate.stacks, stacks, STACK_ALIASES))
        if not active_matches:
            return True
        return all(active_matches) if require_all else any(active_matches)

    def _matched_selections(
        self,
        candidate_values: Sequence[str],
        selections: Sequence[str],
        aliases: Dict[str, tuple[str, ...]],
    ) -> List[str]:
        return [
            selection for selection in selections
            if any(self._match_list(candidate_values, alias) for alias in aliases.get(selection.lower(), (selection,)))
        ]

    def _keyword_hit(self, tags: Sequence[str], description: str, keywords: List[str]) -> bool:
        text = " ".join([" ".join(tags or []), description or ""]).lower()
        return any(k in text for k in keywords)

    def _load_latest_metrics(self, repos: Sequence[str]):
        if not repos:
            return {}, (None, None), (None, None)
        wanted = {"issue_response_time", "change_request_response_time", "issue_age", "change_request_age", "new_contributors", "openrank"}
        ranked = (
            select(
                MetricPoint.repo,
                MetricPoint.metric,
                MetricPoint.dt,
                MetricPoint.value,
                func.row_number().over(
                    partition_by=(MetricPoint.repo, MetricPoint.metric),
                    order_by=MetricPoint.dt.desc(),
                ).label("rn"),
            )
            .where(MetricPoint.repo.in_(repos), MetricPoint.metric.in_(wanted))
        ).subquery()
        latest_rows = self.db.execute(select(ranked).where(ranked.c.rn == 1)).mappings().all()
        values: Dict[str, Dict[str, Any]] = {}
        for row in latest_rows:
            bucket = values.setdefault(row["repo"], {"dt": row["dt"]})
            bucket[row["metric"]] = row["value"]
            if row["dt"] and row["dt"] > bucket["dt"]:
                bucket["dt"] = row["dt"]

        activity_rows = self.db.execute(
            select(MetricPoint.repo, MetricPoint.dt, MetricPoint.value)
            .where(MetricPoint.repo.in_(repos), MetricPoint.metric == "activity")
            .order_by(MetricPoint.repo, MetricPoint.dt)
        ).all()
        activity: Dict[str, List[float]] = {}
        for repo_name, _, value in activity_rows:
            activity.setdefault(repo_name, []).append(float(value or 0))

        metrics_map: Dict[str, RepoMetrics] = {}
        resp_values: List[float] = []
        activity_values: List[float] = []
        for repo_name in repos:
            raw = values.get(repo_name, {})
            series = activity.get(repo_name, [])
            latest_3m = sum(series[-3:]) if series else None
            previous_3m = sum(series[-6:-3]) if len(series) >= 6 else None
            growth = (latest_3m - previous_3m) / previous_3m if latest_3m is not None and previous_3m else None
            metrics = RepoMetrics(
                repo_full_name=repo_name,
                dt=raw.get("dt").isoformat() if raw.get("dt") else None,
                metric_issue_response_time_h=raw.get("issue_response_time"),
                metric_pr_response_time_h=raw.get("change_request_response_time"),
                metric_issue_age_h=raw.get("issue_age"),
                metric_pr_age_h=raw.get("change_request_age"),
                metric_activity_3m=latest_3m,
                metric_activity_growth=growth,
                metric_new_contributors=raw.get("new_contributors"),
                metric_openrank=raw.get("openrank"),
            )
            metrics_map[repo_name] = metrics
            resp_values.extend(value for value in [metrics.metric_issue_response_time_h, metrics.metric_pr_response_time_h, metrics.metric_issue_age_h, metrics.metric_pr_age_h] if value is not None)
            activity_values.extend(value for value in [metrics.metric_activity_3m, metrics.metric_activity_growth, metrics.metric_new_contributors] if value is not None)

        resp_p = (percentile(resp_values, 10), percentile(resp_values, 90))
        activity_p = (percentile(activity_values, 10), percentile(activity_values, 90))
        return metrics_map, resp_p, activity_p

    def _load_issue_stats(self, repos: Sequence[str]) -> Dict[str, IssueStats]:
        if not repos:
            return {}
        rows = self.db.execute(select(RepoIssue).where(RepoIssue.repo_full_name.in_(repos))).scalars()
        stats: Dict[str, IssueStats] = {}
        for item in rows:
            repo_stats = stats.setdefault(item.repo_full_name, IssueStats())
            category = (item.category or "help_wanted").lower()
            if category == "good_first":
                repo_stats.good_first += 1
            elif category == "help_wanted":
                repo_stats.help_wanted += 1
            elif category == "docs":
                repo_stats.docs += 1
            else:
                repo_stats.i18n += 1
            repo_stats.freshness_factor = max(repo_stats.freshness_factor, freshness_score(item.updated_at))
        return stats

    def _load_docs(self, repos: Sequence[str]) -> Dict[str, DocInfo]:
        docs: Dict[str, DocInfo] = {}
        if not repos:
            return docs
        rows = self.db.execute(select(RepoDoc).where(RepoDoc.repo_full_name.in_(repos))).scalars()
        for row in rows:
            docs[row.repo_full_name] = DocInfo(
                repo_full_name=row.repo_full_name,
                readme_text=row.readme_text,
                contributing_text=row.contributing_text,
                pr_template_text=row.pr_template_text,
                extracted=row.extracted or {},
            )
        for repo in repos:
            docs.setdefault(repo, DocInfo(repo_full_name=repo, readme_text=None, contributing_text=None, pr_template_text=None, extracted={}))
        return docs

    def _supply_percentiles(self, stats_map: Dict[str, IssueStats]):
        values: List[float] = []
        for stats in stats_map.values():
            supply_raw = 2 * stats.good_first + 1.5 * stats.help_wanted + 1.0 * stats.docs + 1.0 * stats.i18n
            values.append(math.log1p(supply_raw))
        return (percentile(values, 10), percentile(values, 90))

    # ---------------------------------------------------------
    # Scoring
    # ---------------------------------------------------------
    def _score_candidates(
        self,
        candidates: List[CandidateRepo],
        keywords: List[str],
        domains: Sequence[str],
        stacks: Sequence[str],
        time_per_week: str,
        metrics_map: Dict[str, RepoMetrics],
        issue_stats_map: Dict[str, IssueStats],
        docs_map: Dict[str, DocInfo],
        resp_p: tuple[Optional[float], Optional[float]],
        activity_p: tuple[Optional[float], Optional[float]],
        supply_p: tuple[Optional[float], Optional[float]],
    ) -> List[ScoredRepo]:
        scored: List[ScoredRepo] = []
        for repo in candidates:
            metrics = metrics_map.get(repo.repo_full_name) or RepoMetrics(
                repo_full_name=repo.repo_full_name,
                dt=None,
                metric_issue_response_time_h=None,
                metric_pr_response_time_h=None,
                metric_issue_age_h=None,
                metric_pr_age_h=None,
                metric_activity_3m=None,
                metric_activity_growth=None,
                metric_new_contributors=None,
                metric_openrank=None,
            )
            stats = issue_stats_map.get(repo.repo_full_name, IssueStats())
            doc = docs_map.get(repo.repo_full_name, DocInfo(repo.repo_full_name, None, None, None, {}))

            domain_aliases = [alias for item in domains for alias in DOMAIN_ALIASES.get(item.lower(), (item,))]
            stack_aliases = [alias for item in stacks for alias in STACK_ALIASES.get(item.lower(), (item,))]
            matched_domains = self._matched_selections(repo.domains, domains, DOMAIN_ALIASES)
            matched_stacks = self._matched_selections(repo.stacks, stacks, STACK_ALIASES)
            fit = fit_score(repo, domain_aliases, stack_aliases, keywords)
            readiness = readiness_score(metrics, stats, doc, resp_p, activity_p, supply_p)
            has_profile = bool(domains or stacks or keywords)
            match = 0.55 * fit + 0.45 * readiness if has_profile else readiness
            difficulty = difficulty_label(readiness, time_per_week)
            reasons = []
            if matched_domains:
                reasons.append(f"方向匹配：{'、'.join(matched_domains)}")
            if matched_stacks:
                reasons.append(f"技能匹配：{'、'.join(matched_stacks)}")
            reasons.extend(build_reasons(repo, metrics, stats, readiness, fit)[1:])
            reasons = reasons[:5]
            scored.append(
                ScoredRepo(
                    repo_full_name=repo.repo_full_name,
                    url=repo.url,
                    fit_score=round(fit, 2),
                    readiness_score=round(readiness, 2),
                    match_score=round(match, 2),
                    difficulty=difficulty,
                    responsiveness=metrics.metric_issue_response_time_h,
                    activity=metrics.metric_activity_3m,
                    trend_delta=metrics.metric_activity_growth,
                    reasons=reasons,
                    stats=stats,
                    description=repo.description or "",
                    domains=repo.domains,
                    stacks=repo.stacks,
                    matched_domains=matched_domains,
                    matched_stacks=matched_stacks,
                )
            )

        return sorted(scored, key=lambda x: x.match_score, reverse=True)

    # ---------------------------------------------------------
    # Issues board & timeline
    # ---------------------------------------------------------
    def _issues_board(
        self,
        repo_full_name: Optional[str],
        issue_stats_map: Dict[str, IssueStats],
        scored_repos: List[ScoredRepo],
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not repo_full_name:
            return {}
        readiness_map = {item.repo_full_name: item.readiness_score for item in scored_repos}
        issues = self.db.execute(
            select(RepoIssue).where(RepoIssue.repo_full_name == repo_full_name).order_by(RepoIssue.updated_at.desc())
        ).scalars()
        buckets: Dict[str, List[Dict[str, Any]]] = {"good_first_issue": [], "help_wanted": [], "docs": [], "i18n": []}
        readiness = readiness_map.get(repo_full_name, 60.0)
        for issue in issues:
            category = issue.category or "help_wanted"
            display_bucket = "good_first_issue" if category == "good_first" else category
            score = issue_task_score(issue.updated_at, category, readiness)
            buckets.setdefault(display_bucket, []).append(
                {
                    "title": issue.title,
                    "repo_full_name": repo_full_name,
                    "labels": issue.labels or [],
                    "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
                    "updated_from_now": self._ago(issue.updated_at),
                    "difficulty": issue.difficulty or "Medium",
                    "issue_number": issue.issue_number,
                    "url": issue.url,
                    "score": score,
                }
            )
        for key, items in buckets.items():
            buckets[key] = sorted(items, key=lambda x: x.get("score", 0), reverse=True)[:20]
        return buckets

    def _build_timeline(self, repo: Optional[ScoredRepo], docs: Optional[DocInfo], time_per_week: str) -> List[Dict[str, Any]]:
        if not repo:
            return []
        extracted = docs.extracted if docs else {}
        setup_steps = extracted.get("setup") or self._stack_templates(repo, "setup")
        build_steps = extracted.get("build") or self._stack_templates(repo, "build")
        test_steps = extracted.get("test") or self._stack_templates(repo, "test")
        pr_steps = [
            "Fork 仓库 & 创建分支",
            "提交代码并推送远端",
            "发起 PR，关联 issue",
            "请求评审 & 更新",
            "CI 通过等待合并",
        ]

        return [
            {"title": "Fork", "commands": [f"https://github.com/{repo.repo_full_name}/fork"], "note": "在浏览器完成 fork"},
            {"title": "Clone", "commands": [f"git clone https://github.com/{repo.repo_full_name}.git"], "note": "通用步骤（建议查看仓库文档）"},
            {"title": "Setup", "commands": setup_steps, "note": self._note(extracted)},
            {"title": "Build & Test", "commands": build_steps + test_steps, "note": self._note(extracted)},
            {"title": "First PR", "commands": pr_steps, "note": f"时间档位 {time_per_week}"},
        ]

    def _build_timeline_for_issue(self, repo_full_name: str, docs: RepoDoc, issue: Optional[RepoIssue]) -> List[Dict[str, Any]]:
        extracted = docs.extracted or {}
        setup_steps = extracted.get("setup") or [f"git clone https://github.com/{repo_full_name}.git"]
        build_steps = extracted.get("build") or []
        test_steps = extracted.get("test") or []
        pr_steps = [
            f"git checkout -b fix-issue-{issue.issue_number if issue else 'task'}",
            "git status",
            "git add .",
            "git commit -m 'fix: <summary>'",
            "git push origin HEAD",
            f"在 GitHub 发起 PR 并关联 issue #{issue.issue_number if issue else ''}",
        ]
        return [
            {"title": "Setup", "commands": setup_steps, "note": self._note(extracted)},
            {"title": "Build", "commands": build_steps, "note": self._note(extracted)},
            {"title": "Test", "commands": test_steps or ["(可选) 依据仓库文档执行测试"], "note": self._note(extracted)},
            {"title": "PR", "commands": pr_steps, "note": "提交 PR 并请求评审"},
        ]

    def _note(self, extracted: Dict[str, Any]) -> str:
        return "仓库抽取命令" if extracted else "通用步骤（建议查看仓库文档）"

    def _stack_templates(self, repo: ScoredRepo, stage: str) -> List[str]:
        stack_lower = "".join(repo.reasons).lower()
        if "python" in stack_lower:
            templates = {
                "setup": ["python -m venv .venv", "source .venv/bin/activate", "pip install -r requirements.txt"],
                "build": ["pytest"],
                "test": [],
            }
        elif "go" in stack_lower:
            templates = {"setup": ["go mod download"], "build": ["go test ./..."], "test": []}
        else:
            templates = {
                "setup": ["npm install"],
                "build": ["npm run build"],
                "test": ["npm test"],
            }
        return templates.get(stage, [])

    # ---------------------------------------------------------
    # Rendering helpers
    # ---------------------------------------------------------
    def _render_checklist(self, repo: Optional[ScoredRepo], timeline: List[Dict[str, Any]]) -> str:
        if not repo:
            return ""
        lines = [f"## {repo.repo_full_name} 贡献清单", ""]
        for step in timeline:
            lines.append(f"### {step['title']}")
            for cmd in step.get("commands", []):
                lines.append(f"- {cmd}")
            if step.get("note"):
                lines.append(f"> {step['note']}")
            lines.append("")
        return "\n".join(lines).strip()

    def _render_issue_checklist(self, repo_full_name: str, issue: Optional[RepoIssue], steps: List[Dict[str, Any]]) -> str:
        title = issue.title if issue else "任务步骤"
        lines = [f"## {repo_full_name} · {title}", ""]
        for step in steps:
            lines.append(f"### {step['title']}")
            for cmd in step.get("commands", []):
                lines.append(f"- {cmd}")
            if step.get("note"):
                lines.append(f"> {step['note']}")
            lines.append("")
        if issue:
            lines.append(f"PR 模板：\n- 关联 issue #{issue.issue_number}\n- 描述变更、测试结果、影响范围")
        return "\n".join(lines).strip()

    def _serialize_repo(self, scored: ScoredRepo, rank: Optional[int] = None) -> Dict[str, Any]:
        payload = asdict(scored)
        payload["stats"] = asdict(scored.stats) if scored.stats else {}
        if rank is not None:
            payload["rank"] = rank
        return payload

    def _ago(self, updated_at: Optional[datetime]) -> str:
        if not updated_at:
            return ""
        delta = datetime.utcnow() - updated_at
        days = delta.days
        if days <= 0:
            hours = delta.seconds // 3600
            return f"{hours} 小时前" if hours > 0 else "刚刚"
        return f"{days} 天前"
