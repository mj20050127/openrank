from app.schemas.requests import NewcomerPlanRequest
from app.services.newcomer_plan import DOMAIN_ALIASES, NewcomerPlanService
from app.services.newcomer_scoring import CandidateRepo, fit_score


def candidate(*, domains=None, stacks=None):
    return CandidateRepo(
        repo_full_name="example/project",
        url="https://github.com/example/project",
        domains=domains or [],
        stacks=stacks or [],
        tags=[],
        description="",
    )


def test_newcomer_request_accepts_multi_select_and_legacy_scalars():
    multi = NewcomerPlanRequest(
        domains=["frontend", "ai_ml"],
        stacks=["javascript", "python"],
        time_per_week="3-5h",
    )
    assert multi.domains == ["frontend", "ai_ml"]
    assert multi.stacks == ["javascript", "python"]

    legacy = NewcomerPlanRequest(domain="frontend", stack="javascript", time_per_week="1-2h")
    assert legacy.domain == "frontend"
    assert legacy.stack == "javascript"


def test_fit_score_normalizes_active_weights_for_multi_select():
    repo = candidate(domains=["frontend"], stacks=["javascript"])
    assert fit_score(repo, ["frontend", "ai-data"], ["javascript", "python"], []) == 100.0

    partial = fit_score(repo, ["frontend"], ["python"], [])
    assert round(partial, 2) == 53.33


def test_fit_score_does_not_treat_java_as_javascript():
    repo = candidate(domains=["backend"], stacks=["javascript"])
    score = fit_score(repo, ["backend"], ["java"], [])
    assert round(score, 2) == 53.33


def test_domain_aliases_match_catalog_categories():
    service = NewcomerPlanService(db=None, fetcher=object())
    assert service._matches_selection(["ai-data"], ["ai_ml"], DOMAIN_ALIASES)
    assert service._matches_selection(["cloud-observability"], ["cloud_infra"], DOMAIN_ALIASES)
    assert not service._matches_selection(["security"], ["frontend"], DOMAIN_ALIASES)


def test_dedupe_preserves_selection_order():
    assert NewcomerPlanService._dedupe(["frontend", "Frontend", "", "ai_ml"]) == ["frontend", "ai_ml"]

def test_profile_match_treats_empty_selections_as_all():
    service = NewcomerPlanService(db=None, fetcher=object())
    repo = candidate(domains=["frontend"], stacks=["javascript"])

    assert service._matches_profile(repo, [], [], require_all=True)
    assert service._matches_profile(repo, [], ["javascript"], require_all=True)
    assert service._matches_profile(repo, ["frontend"], [], require_all=True)


def test_relaxed_profile_match_accepts_domain_or_stack():
    service = NewcomerPlanService(db=None, fetcher=object())
    repo = candidate(domains=["frontend"], stacks=["javascript"])

    assert not service._matches_profile(repo, ["ai_ml"], ["javascript"], require_all=True)
    assert service._matches_profile(repo, ["ai_ml"], ["javascript"], require_all=False)


