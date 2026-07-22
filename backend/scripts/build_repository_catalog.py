from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
import math
import os
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db.base import SessionLocal
from app.db.init_db import init_db
from app.db.models import RepositoryDataStatus
from app.models import RepoCatalog
from app.services.monthly_ingestion import normalize_monthly_payload

QUOTAS = {
    "frontend": 55,
    "backend": 60,
    "ai-data": 60,
    "cloud-observability": 60,
    "database-data-infra": 45,
    "mobile": 35,
    "systems-runtime": 45,
    "security": 40,
    "developer-tools": 45,
    "docs-i18n-community": 30,
    "oss-analytics-education": 25,
}
SEARCH_TOPICS = {
    "frontend": ["frontend", "react", "vue", "web-framework"],
    "backend": ["backend", "web-framework", "api", "microservices"],
    "ai-data": ["machine-learning", "deep-learning", "data-science", "llm"],
    "cloud-observability": ["cloud-native", "kubernetes", "observability", "devops"],
    "database-data-infra": ["database", "data-engineering", "streaming", "distributed-database"],
    "mobile": ["android", "ios", "flutter", "mobile"],
    "systems-runtime": ["programming-language", "compiler", "operating-system", "runtime"],
    "security": ["security", "cybersecurity", "vulnerability", "supply-chain-security"],
    "developer-tools": ["developer-tools", "ide", "build-tool", "cli"],
    "docs-i18n-community": ["documentation", "internationalization", "localization", "static-site-generator"],
    "oss-analytics-education": ["open-source", "github-analytics", "education", "awesome-list"],
}
LEGACY_CATEGORY = {
    "ai": "ai-data", "cloud": "cloud-observability", "docs": "docs-i18n-community",
    "i18n": "docs-i18n-community", "oss-analytics": "oss-analytics-education",
}


def _headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN") or settings.GITHUB_TOKEN
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to build the 500-repository catalog")
    return {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "User-Agent": "OpenSage-catalog-builder/1.0"}


def _official_repos(client: httpx.Client) -> set[str]:
    response = client.get("https://oss.open-digger.cn/repo_list.csv")
    response.raise_for_status()
    rows = csv.reader(response.text.splitlines())
    return {row[2] for row in rows if len(row) >= 3 and row[1].lower() == "github"}


def _github_candidates(client: httpx.Client, official: set[str]) -> dict[str, dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=365)).date().isoformat()
    candidates: dict[str, dict[str, Any]] = {}
    for category, topics in SEARCH_TOPICS.items():
        for topic in topics:
            params = {"q": f"topic:{topic} stars:>300 archived:false fork:false pushed:>={cutoff}", "sort": "stars", "order": "desc", "per_page": 100}
            response = client.get("https://api.github.com/search/repositories", params=params, headers=_headers())
            response.raise_for_status()
            for item in response.json().get("items", []):
                name = item.get("full_name")
                if name in official:
                    current = candidates.setdefault(name, {**item, "category_votes": Counter()})
                    current["category_votes"][category] += 1
    return candidates


def _merge_existing(candidates: dict[str, dict[str, Any]], official: set[str]) -> None:
    with SessionLocal() as db:
        rows = db.execute(select(RepoCatalog)).scalars().all()
    for row in rows:
        if row.repo_full_name not in official:
            continue
        category = LEGACY_CATEGORY.get(row.seed_domain, row.seed_domain)
        if category not in QUOTAS:
            category = "developer-tools"
        item = candidates.setdefault(
            row.repo_full_name,
            {
                "full_name": row.repo_full_name,
                "description": row.description,
                "language": row.primary_language,
                "topics": row.topics or [],
                "stargazers_count": row.stars or 0,
                "forks_count": row.forks or 0,
                "open_issues_count": row.open_issues_count or 0,
                "pushed_at": row.pushed_at.isoformat() if row.pushed_at else None,
                "archived": False,
                "fork": False,
                "has_issues": True,
                "license": {"spdx_id": row.license} if row.license else None,
                "category_votes": Counter(),
            },
        )
        item["category_votes"][category] += 3


def _enrich(repo: str) -> dict[str, Any]:
    result = {"repo": repo, "months": 0, "openrank": 0.0, "activity": 0.0, "series_available": 0, "region": "global"}
    with httpx.Client(timeout=30, verify=False, trust_env=False, follow_redirects=True) as client:
        months: set[str] = set()
        for metric, filename in (("openrank", "openrank.json"), ("activity", "activity.json"), ("stars", "stars.json")):
            response = client.get(f"https://oss.open-digger.cn/github/{repo}/{filename}")
            if response.status_code == 404:
                continue
            response.raise_for_status()
            records = normalize_monthly_payload(metric, response.json())
            if records:
                result[metric] = list(records.values())[-1]
                months.update(value.isoformat() for value in records)
                result["series_available"] += 1
        result["months"] = len(months)
        meta = client.get(f"https://oss.open-digger.cn/github/{repo}/meta.json")
        if meta.status_code == 200:
            labels = meta.json().get("labels") or []
            if any(str(label.get("id", "")).lower() == ":regions/cn" for label in labels if isinstance(label, dict)):
                result["region"] = "CN"
    return result


def _score(item: dict[str, Any], enriched: dict[str, Any]) -> float:
    influence = min(1.0, math.log1p(enriched["openrank"] + enriched["activity"]) / math.log1p(11000))
    popularity = min(1.0, math.log1p(item.get("stargazers_count") or 0) / math.log1p(200000))
    history = min(1.0, enriched["months"] / 120)
    newcomer = min(1.0, (item.get("open_issues_count") or 0) / 50) * 0.5
    newcomer += 0.25 if item.get("has_issues") else 0
    newcomer += 0.25 if item.get("license") else 0
    coverage = enriched["series_available"] / 3
    return round(100 * (influence * 0.30 + popularity * 0.20 + history * 0.20 + newcomer * 0.20 + coverage * 0.10), 3)


def _select_category(items: list[dict[str, Any]], quota: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    owner_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    language_limit = max(1, math.floor(quota * 0.35))
    cn_target = math.ceil(quota * 0.15)
    ordered = sorted(items, key=lambda item: (-item["selection_score"], item["repo"]))
    cn_first = [item for item in ordered if item["region"] == "CN"] + [item for item in ordered if item["region"] != "CN"]
    for item in cn_first:
        if len(selected) >= quota:
            break
        owner = item["repo"].split("/", 1)[0].lower()
        language = (item.get("language") or "unknown").lower()
        need_cn = sum(1 for value in selected if value["region"] == "CN") < cn_target
        if need_cn and item["region"] != "CN" and any(value["region"] == "CN" for value in ordered if value not in selected):
            continue
        if owner_counts[owner] >= 5 or language_counts[language] >= language_limit:
            continue
        selected.append(item)
        owner_counts[owner] += 1
        language_counts[language] += 1
    if len(selected) != quota:
        raise RuntimeError(f"category quota cannot be satisfied: wanted {quota}, got {len(selected)}")
    return selected


def _write_csv(path: Path, selected: list[dict[str, Any]]) -> None:
    fields = ["repo", "category", "language", "region", "maturity", "selection_score", "months", "stars", "selection_reason", "opendigger_supported"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in selected:
            writer.writerow({key: item.get(key) for key in fields})


def _apply(selected: list[dict[str, Any]]) -> None:
    with SessionLocal() as db:
        for row in db.execute(select(RepositoryDataStatus).where(RepositoryDataStatus.scope == "curated")).scalars():
            row.scope = "legacy"
            row.enabled = False
        for item in selected:
            row = db.get(RepositoryDataStatus, item["repo"])
            if row is None:
                row = RepositoryDataStatus(repo=item["repo"], sync_status="pending")
                db.add(row)
            row.scope = "curated"
            row.enabled = True
            row.opendigger_supported = True
            metadata = dict(row.metadata_json or {})
            metadata.update({"category": item["category"], "region": item["region"], "maturity": item["maturity"], "selection_score": item["selection_score"]})
            row.metadata_json = metadata
        db.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the deterministic 500-repository OpenSage catalog")
    parser.add_argument("--output", type=Path, default=Path("data/repositories_500.csv"))
    parser.add_argument("--apply", action="store_true", help="replace the active curated scope after writing CSV")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    init_db()
    with httpx.Client(timeout=30, verify=False, trust_env=False, follow_redirects=True) as client:
        official = _official_repos(client)
        candidates = _github_candidates(client, official)
    _merge_existing(candidates, official)

    enriched: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 8))) as pool:
        futures = {pool.submit(_enrich, repo): repo for repo in candidates}
        for future in as_completed(futures):
            repo = futures[future]
            try:
                enriched[repo] = future.result()
            except Exception as exc:
                print(f"skip {repo}: {exc}")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for repo, item in candidates.items():
        info = enriched.get(repo)
        if not info or info["months"] < 24 or item.get("archived") or item.get("fork"):
            continue
        category = item["category_votes"].most_common(1)[0][0]
        row = {
            "repo": repo,
            "category": category,
            "language": item.get("language") or "Unknown",
            "region": info["region"],
            "selection_score": _score(item, info),
            "months": info["months"],
            "stars": item.get("stargazers_count") or 0,
            "selection_reason": "领域配额+影响力+历史连续性+新人友好度",
            "opendigger_supported": True,
        }
        grouped[category].append(row)

    selected: list[dict[str, Any]] = []
    for category, quota in QUOTAS.items():
        category_rows = _select_category(grouped[category], quota)
        for index, row in enumerate(category_rows):
            percentile = (index + 1) / quota
            row["maturity"] = "landmark" if percentile <= 0.30 else "established" if percentile <= 0.70 else "growing"
        selected.extend(category_rows)
    if len(selected) != 500 or sum(1 for item in selected if item["region"] == "CN") < 75:
        raise RuntimeError("catalog invariants failed: expected 500 repositories and at least 75 CN projects")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output, sorted(selected, key=lambda item: (item["category"], -item["selection_score"])))
    if args.apply:
        _apply(selected)
    print({"output": str(args.output), "repositories": len(selected), "cn": sum(1 for item in selected if item["region"] == "CN"), "applied": args.apply})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())