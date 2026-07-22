import unittest

from app.services.ecosystem_graph import aggregate_contribution_counts, contributor_avatar_url


class ContributorAvatarUrlTests(unittest.TestCase):
    def test_prefers_github_graphql_url(self):
        avatar = "https://avatars.githubusercontent.com/u/1?v=4"
        self.assertEqual(contributor_avatar_url("octocat", avatar), avatar)

    def test_falls_back_to_login_image(self):
        self.assertEqual(
            contributor_avatar_url("octocat"),
            "https://avatars.githubusercontent.com/octocat?s=192",
        )

    def test_rejects_invalid_login(self):
        self.assertIsNone(contributor_avatar_url("not/a/login"))


class AggregateContributionCountsTests(unittest.TestCase):
    def test_sums_verified_github_counts_across_repositories(self):
        self.assertEqual(
            aggregate_contribution_counts({
                "kubernetes/enhancements": {"commits": 7, "pull_requests": 0, "reviews": 4, "issues": 0},
                "kubernetes/code-generator": {"commits": 8, "pull_requests": 0, "reviews": 0, "issues": 0},
                "kubernetes/website": {"commits": 4, "pull_requests": 1, "reviews": 0, "issues": 0},
            }),
            {"commits": 19, "pull_requests": 1, "reviews": 4, "issues": 0},
        )

    def test_preserves_unavailable_state_without_verified_repositories(self):
        self.assertIsNone(aggregate_contribution_counts({}))
if __name__ == "__main__":
    unittest.main()

