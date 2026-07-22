from __future__ import annotations

import unittest
from datetime import date

from app.services.monthly_ingestion import normalize_monthly_payload
from app.services.ecosystem_graph import contribution_score, contributor_role
from app.services.historical_audit import _normalize_scorecard_record, analyze_workflows, classify_repository_paths
from app.services.monthly_scoring import _dimension_scores, _month_range
from app.services.current_health import compute_current_scores


class MonthlyPayloadTests(unittest.TestCase):
    def test_numeric_months_are_preserved(self):
        payload = {"2024-01": 1, "2024-02": 2.5, "meta": 99}
        self.assertEqual(
            normalize_monthly_payload("activity", payload),
            {date(2024, 1, 1): 1.0, date(2024, 2, 1): 2.5},
        )

    def test_known_contributor_lists_become_counts(self):
        payload = {"2024-01": ["a", "b"], "2024-02": []}
        self.assertEqual(
            normalize_monthly_payload("contributors", payload),
            {date(2024, 1, 1): 2.0, date(2024, 2, 1): 0.0},
        )

    def test_structured_unknown_values_are_not_flattened(self):
        payload = {"2024-01": [{"name": "a"}]}
        self.assertEqual(normalize_monthly_payload("activity", payload), {})

    def test_avg_export_is_supported(self):
        payload = {"avg": {"2024-03": 12.5}}
        self.assertEqual(normalize_monthly_payload("issue_response_time", payload), {date(2024, 3, 1): 12.5})


class EcosystemScoringTests(unittest.TestCase):
    def test_contribution_formula_uses_central_weights(self):
        self.assertEqual(
            contribution_score({"commits": 10, "pull_requests": 2, "reviews": 3, "issues": 4}),
            26.0,
        )

    def test_missing_contribution_component_stays_missing(self):
        self.assertIsNone(
            contribution_score({"commits": 10, "pull_requests": None, "reviews": 3, "issues": 4})
        )
    def test_roles_are_relative_to_snapshot_window(self):
        self.assertEqual(contributor_role(is_new=True, stale_months=0, rank=8, population=20), "new")
        self.assertEqual(contributor_role(is_new=False, stale_months=0, rank=0, population=20), "core")
        self.assertEqual(contributor_role(is_new=False, stale_months=1, rank=8, population=20), "active")
        self.assertEqual(contributor_role(is_new=False, stale_months=2, rank=8, population=20), "risk")
        self.assertEqual(contributor_role(is_new=False, stale_months=4, rank=8, population=20), "inactive")

class MonthlyScoringTests(unittest.TestCase):
    def test_month_range_is_continuous(self):
        self.assertEqual(
            _month_range(date(2023, 11, 1), date(2024, 2, 1)),
            [date(2023, 11, 1), date(2023, 12, 1), date(2024, 1, 1), date(2024, 2, 1)],
        )

    def test_community_score_uses_only_current_and_past_months(self):
        months = _month_range(date(2024, 1, 1), date(2024, 7, 1))
        pivot = {}
        for index, month in enumerate(months, start=1):
            pivot[month] = {
                "openrank": 100 + index,
                "activity": 500 + index * 10,
                "contributors": 40,
                "new_contributors": 8,
                "inactive_contributors": 5,
                "bus_factor": 6,
                "issues_new": 20,
                "issues_closed": 18,
                "issue_response_time": 24,
                "change_requests": 15,
                "change_requests_accepted": 12,
                "change_requests_reviews": 12,
                "change_request_response_time": 18,
            }
        before = _dimension_scores(pivot, months, 5)
        pivot[months[6]]["activity"] = 999999
        after = _dimension_scores(pivot, months, 5)
        self.assertEqual(before["community"], after["community"])
        self.assertIsNotNone(after["community"])


class HistoricalAuditTests(unittest.TestCase):
    def test_governance_paths_are_classified_at_snapshot(self):
        result = classify_repository_paths([
            "README.md",
            "LICENSE",
            ".github/CONTRIBUTING.md",
            ".github/SECURITY.md",
            ".github/ISSUE_TEMPLATE/bug.yml",
            ".github/PULL_REQUEST_TEMPLATE.md",
            ".github/dependabot.yml",
            ".github/workflows/codeql.yml",
        ])
        self.assertTrue(result["files"]["readme"])
        self.assertTrue(result["files"]["security"])
        self.assertTrue(result["files"]["issue_template"])
        self.assertTrue(result["dependency_update"])
        self.assertEqual(result["workflow_paths"], [".github/workflows/codeql.yml"])

    def test_workflow_security_uses_historical_content(self):
        sha = "a" * 40
        result = analyze_workflows({
            ".github/workflows/security.yml": """steps:
  - uses: github/codeql-action/init@v3
  - uses: actions/checkout@{sha}
""".format(sha=sha)
        })
        self.assertTrue(result["sast"])
        self.assertEqual(result["action_references"], 2)
        self.assertEqual(result["pinned_action_references"], 1)
        self.assertEqual(result["workflow_hygiene_score"], 50.0)

    def test_scorecard_export_keeps_historical_date(self):
        record = _normalize_scorecard_record(
            {"repo": "github.com/example/project", "date": "2026-02-20", "score": 7.5, "checks": []}
        )
        self.assertEqual(record["repo"], "example/project")
        self.assertEqual(record["date"], "2026-02-20")
        self.assertEqual(record["score"], 75.0)

class CurrentHealthTests(unittest.TestCase):
    def evidence(self):
        return {
            "observed_at": "2026-07-15T00:00:00+00:00",
            "metadata": {
                "pushed_at": "2026-07-14T00:00:00Z",
                "updated_at": "2026-07-14T00:00:00Z",
                "stars": 1000,
                "forks": 100,
                "archived": False,
            },
            "activity": {
                "commits_current": 120,
                "commits_previous": 100,
                "active_weeks": 13,
                "weeks_observed": 13,
            },
            "collaboration": {
                "issues_opened": 30,
                "issues_opened_previous": 25,
                "issues_closed": 28,
                "prs_opened": 24,
                "prs_opened_previous": 20,
                "prs_merged": 22,
                "open_issue_median_age_days": 20,
                "open_pr_median_age_days": 10,
                "open_issue_age_sample": 30,
                "open_pr_age_sample": 24,
            },
            "contributors": {
                "active_contributors": 25,
                "bus_factor": 5,
                "top1_share": 0.2,
                "total_contributions": 120,
            },
            "governance": {
                "files": {
                    "readme": True,
                    "license": True,
                    "contributing": True,
                    "code_of_conduct": True,
                    "security": True,
                    "issue_template": True,
                    "pull_request_template": True,
                    "governance": True,
                    "codeowners": True,
                },
                "dependency_update": True,
                "workflows": {
                    "sast": True,
                    "workflow_hygiene_score": 100.0,
                },
            },
        }

    def test_complete_current_evidence_produces_five_dimension_score(self):
        scorecard = {
            "score": 8.5,
            "checks": {
                "Dependency-Update-Tool": {"score": 10},
                "SAST": {"score": 9},
                "Pinned-Dependencies": {"score": 8},
            },
        }
        result = compute_current_scores(self.evidence(), scorecard)
        self.assertIsNotNone(result["comprehensive"])
        self.assertGreaterEqual(result["completeness"], 0.8)
        self.assertEqual(set(result["scores"]), {
            "vitality", "responsiveness", "resilience", "governance", "security"
        })

    def test_missing_scorecard_does_not_fake_comprehensive_score(self):
        evidence = self.evidence()
        evidence["governance"]["files"]["security"] = False
        evidence["governance"]["dependency_update"] = False
        evidence["governance"]["workflows"] = {
            "sast": False,
            "workflow_hygiene_score": None,
        }
        result = compute_current_scores(evidence, {"score": None, "checks": {}})
        self.assertIsNone(result["scores"]["security"])
        self.assertIsNone(result["comprehensive"])
if __name__ == "__main__":
    unittest.main()