from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.base import SessionLocal
from app.services.github_fetch import GitHubFetchService


def _repositories(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh GitHub issue and onboarding-document data for the grading snapshot"
    )
    parser.add_argument(
        "--repos-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "repos.txt",
    )
    args = parser.parse_args()

    results = []
    with SessionLocal() as db:
        fetcher = GitHubFetchService(
            db,
            issue_ttl_hours=0,
            content_ttl_hours=0,
        )
        for repository in _repositories(args.repos_file):
            issue_groups = fetcher.refresh_repo_issues(repository)
            document = fetcher.refresh_repo_docs(repository)
            results.append(
                {
                    "repo": repository,
                    "issues": sum(len(items) for items in issue_groups.values()),
                    "has_readme": bool(document.readme_text),
                    "has_contributing": bool(document.contributing_text),
                    "has_pr_template": bool(document.pr_template_text),
                }
            )
            print(json.dumps(results[-1], ensure_ascii=False))

    print(json.dumps({"repositories": len(results), "data": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
