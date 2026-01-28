from __future__ import annotations

import math
import re
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import HealthOverviewDaily
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


class NewcomerPlanService:
    """Recall → Score → Assemble recommendation + issues + timeline."""

    RECALL_LIMIT = 30
    RETURN_LIMIT = 6

    def __init__(self, db: Session, fetcher: Optional[GitHubFetchService] = None) -> None:
        self.db = db
        self.fetcher = fetcher or GitHubFetchService(db)

    # ---------------------------------------------------------
    # Public orchestrations
    # ---------------------------------------------------------
    def build_plan(self, domain: str, stack: str, time_per_week: str, keywords: str) -> Dict[str, Any]:
        keyword_list = [k.strip().lower() for k in re.split(r"[\s,]+", keywords or "") if k.strip()]
        candidates = self._recall_candidates(domain, stack, keyword_list)
        if not candidates:
            return {"recommended_repos": [], "issues_board": {}, "timeline": [], "explain": {}, "copyable_checklist": ""}

        # Warm caches for candidates (TTL protected)
        for repo in candidates[: self.RECALL_LIMIT]:
            self.fetcher.refresh_repo_issues(repo.repo_full_name)
            self.fetcher.refresh_repo_docs(repo.repo_full_name)

        repo_names = [c.repo_full_name for c in candidates]
        metrics_map, resp_p, activity_p = self._load_latest_metrics(repo_names)
        issue_stats_map = self._load_issue_stats(repo_names)
        docs_map = self._load_docs(repo_names)
        supply_p = self._supply_percentiles(issue_stats_map)

        scored = self._score_candidates(
            candidates, keyword_list, domain, stack, time_per_week, metrics_map, issue_stats_map, docs_map, resp_p, activity_p, supply_p
        )

        top_repo = scored[0] if scored else None
        issues_board = self._issues_board(top_repo.repo_full_name if top_repo else None, issue_stats_map, scored)
        timeline = self._build_timeline(top_repo, docs_map.get(top_repo.repo_full_name) if top_repo else None, time_per_week)
        checklist = self._render_checklist(top_repo, timeline)

        return {
            "profile": {
                "domain": domain,
                "stack": stack,
                "time_per_week": time_per_week,
                "keywords": keywords,
            },
            "recommended_repos": [self._serialize_repo(s) for s in scored[: self.RETURN_LIMIT]],
            "issues_board": issues_board,
            "timeline": timeline,
            "explain": {"why": top_repo.reasons if top_repo else []},
            "copyable_checklist": checklist,
        }

    def get_repo_issues(self, repo_full_name: str, readiness: float = 60.0) -> Dict[str, List[Dict[str, Any]]]:
        self.fetcher.refresh_repo_issues(repo_full_name)
        issue_stats_map = self._load_issue_stats([repo_full_name])
        scored_repos = [ScoredRepo(repo_full_name=repo_full_name, url=None, fit_score=0, readiness_score=readiness, match_score=readiness, difficulty="", responsiveness=None, activity=None, trend_delta=0, reasons=[], stats=issue_stats_map.get(repo_full_name, IssueStats()))]
        return self._issues_board(repo_full_name, issue_stats_map, scored_repos)

    def build_task_bundle(self, repo_full_name: str, issue_identifier: str | int) -> Dict[str, Any]:
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
    def _recall_candidates(self, domain: str, stack: str, keywords: List[str]) -> List[CandidateRepo]:
        # widen recall window to scan more rows
        rows = self.db.execute(select(RepoCatalog).order_by(RepoCatalog.repo_full_name).limit(self.RECALL_LIMIT * 5)).scalars().all()
        domain_lower = (domain or "").lower()
        stack_lower = (stack or "").lower()

        def build_candidate(row) -> CandidateRepo:
            domains = row.domains or row.topics or ([row.seed_domain] if getattr(row, "seed_domain", None) else [])
            stacks = row.stacks or ([row.primary_language] if row.primary_language else [])
            return CandidateRepo(
                repo_full_name=row.repo_full_name,
                url=f"https://github.com/{row.repo_full_name}",
                domains=domains or [],
                stacks=stacks or [],
                tags=row.tags or [],
                description=row.description or "",
                seed_domain=row.seed_domain,
            )

        def strict_match(c: CandidateRepo) -> bool:
            if domain_lower and not self._match_list(c.domains, domain_lower):
                return False
            if stack_lower and not self._match_list(c.stacks, stack_lower):
                return False
            if keywords and not self._keyword_hit(c.tags, c.description, keywords):
                return False
            return True

        def relaxed_match(c: CandidateRepo) -> bool:
            domain_hit = not domain_lower or self._match_list(c.domains, domain_lower)
            stack_hit = not stack_lower or self._match_list(c.stacks, stack_lower)
            if not (domain_hit or stack_hit):
                return False
            if keywords and not self._keyword_hit(c.tags, c.description, keywords):
                return False
            return True

        candidates_all = [build_candidate(r) for r in rows]
        # cap candidates to avoid slow scoring when domain/stack过宽
        if len(candidates_all) > 80:
            candidates_all = candidates_all[:80]
        strict_results = [c for c in candidates_all if strict_match(c)]
        if len(strict_results) >= self.RETURN_LIMIT:
            return strict_results[: self.RECALL_LIMIT]

        relaxed_results = strict_results[:]
        for c in candidates_all:
            if c in relaxed_results:
                continue
            if relaxed_match(c):
                relaxed_results.append(c)
            if len(relaxed_results) >= self.RECALL_LIMIT:
                break

        if len(relaxed_results) >= self.RETURN_LIMIT:
            return relaxed_results[: self.RECALL_LIMIT]

        # Fallback: fill up with remaining repos even无匹配，以保证有足够候选
        filler = [c for c in candidates_all if c not in relaxed_results]
        return (relaxed_results + filler)[: self.RECALL_LIMIT]

    def _match_list(self, values: Sequence[str], target: str) -> bool:
        t = target.lower()
        return any(t == v.lower() or t in v.lower() or v.lower() in t for v in values or [])

    def _keyword_hit(self, tags: Sequence[str], description: str, keywords: List[str]) -> bool:
        text = " ".join([" ".join(tags or []), description or ""]).lower()
        return any(k in text for k in keywords)

    def _load_latest_metrics(self, repos: Sequence[str]):
        if not repos:
            return {}, (None, None), (None, None)
        ho = HealthOverviewDaily
        ranked = (
            select(
                ho.repo_full_name,
                ho.dt,
                ho.metric_issue_response_time_h,
                ho.metric_pr_response_time_h,
                ho.metric_issue_age_h,
                ho.metric_pr_age_h,
                ho.metric_activity_3m,
                ho.metric_activity_growth,
                ho.metric_new_contributors,
                ho.metric_openrank,
                func.row_number().over(partition_by=ho.repo_full_name, order_by=ho.dt.desc()).label("rn"),
            )
            .where(ho.repo_full_name.in_(repos))
        ).subquery()

        rows = self.db.execute(select(ranked).where(ranked.c.rn == 1)).mappings()
        metrics_map: Dict[str, RepoMetrics] = {}
        resp_values: List[float] = []
        activity_values: List[float] = []
        for row in rows:
            metrics = RepoMetrics(
                repo_full_name=row["repo_full_name"],
                dt=row["dt"].isoformat() if row["dt"] else None,
                metric_issue_response_time_h=row["metric_issue_response_time_h"],
                metric_pr_response_time_h=row["metric_pr_response_time_h"],
                metric_issue_age_h=row["metric_issue_age_h"],
                metric_pr_age_h=row["metric_pr_age_h"],
                metric_activity_3m=row["metric_activity_3m"],
                metric_activity_growth=row["metric_activity_growth"],
                metric_new_contributors=row["metric_new_contributors"],
                metric_openrank=row["metric_openrank"],
            )
            metrics_map[row["repo_full_name"]] = metrics
            for value in [metrics.metric_issue_response_time_h, metrics.metric_pr_response_time_h, metrics.metric_issue_age_h, metrics.metric_pr_age_h]:
                if value is not None:
                    resp_values.append(value)
            for value in [metrics.metric_activity_3m, metrics.metric_activity_growth, metrics.metric_new_contributors]:
                if value is not None:
                    activity_values.append(value)

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
        domain: str,
        stack: str,
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

            fit = fit_score(repo, domain, stack, keywords)
            readiness = readiness_score(metrics, stats, doc, resp_p, activity_p, supply_p)
            match = 0.55 * fit + 0.45 * readiness
            difficulty = difficulty_label(readiness, time_per_week)
            reasons = build_reasons(repo, metrics, stats, readiness, fit)
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
                    trend_delta=metrics.metric_activity_growth or 0.0,
                    reasons=reasons,
                    stats=stats,
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

    def _serialize_repo(self, scored: ScoredRepo) -> Dict[str, Any]:
        payload = asdict(scored)
        payload["stats"] = asdict(scored.stats) if scored.stats else {}
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
