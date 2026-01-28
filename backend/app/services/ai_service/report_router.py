"""Report router for AI service."""

import time
from typing import Dict, Any
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.config import settings
from app.db.base import get_db
from app.services.ai_service.llm_client import llm_client
from app.services.ai_service.facts.health_facts import create_health_facts_extractor
from app.services.ai_service.facts.newcomer_facts import create_newcomer_facts_extractor
from app.services.ai_service.facts.trend_facts import create_trend_facts_extractor
from app.services.ai_service.validators.evidence_check import create_evidence_checker
from app.services.ai_service.render.markdown import create_markdown_renderer
from app.services.ai_service.cache import cache_manager
from app.services.ai_service.validators.schema import (
    HealthReportRequest,
    NewcomerReportRequest,
    TrendReportRequest,
    ReportResponse
)


router = APIRouter()


def generate_report(module: str, params: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Generate report for a module.

    Args:
        module: Report module (health, newcomer, trend)
        params: Report parameters
        db: Database session

    Returns:
        Generated report with markdown and meta information
    """
    start_time = time.time()
    cached = False

    # Generate cache key
    cache_key = cache_manager.get_report_key(module, **params)
    
    # Check cache
    cached_report = cache_manager.get(cache_key)
    if cached_report:
        cached = True
        return cached_report

    # Extract facts based on module
    if module == "health":
        facts = _extract_health_facts(params, db)
        prompt_template = _load_prompt_template("health")
    elif module == "newcomer":
        facts = _extract_newcomer_facts(params, db)
        prompt_template = _load_prompt_template("newcomer")
    elif module == "trend":
        facts = _extract_trend_facts(params, db)
        prompt_template = _load_prompt_template("trend")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid module: {module}"
        )

    # Generate report using LLM
    report_json = llm_client.generate_report(module, facts, prompt_template)
    
    # Add module and params to report_json
    report_json["module"] = module
    if "repo_full_name" in params:
        report_json["repo"] = params["repo_full_name"]
    if "time_window_days" in params:
        report_json["time_window_days"] = params["time_window_days"]
    
    # Validate evidence
    evidence_checker = create_evidence_checker(facts)
    validation_result = evidence_checker.validate_report(report_json)
    
    if not validation_result["valid"]:
        # Add validation errors to warnings
        for error in validation_result["errors"]:
            report_json.setdefault("warnings", []).append(f"Validation error: {error}")
    
    # Render markdown
    renderer = create_markdown_renderer(module)
    report_markdown = renderer.render(report_json)
    
    # Prepare response
    response = {
        "report_json": report_json,
        "report_markdown": report_markdown,
        "meta": {
            "model": "MaxKB",
            "cached": cached,
            "cost_ms": int((time.time() - start_time) * 1000),
            "validation_errors": validation_result["errors"],
            "validation_warnings": validation_result["warnings"]
        }
    }
    
    # Cache the result
    cache_manager.set(cache_key, response, cache_manager.ai_reports_ttl)
    
    return response


def _extract_health_facts(params: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Extract health facts.

    Args:
        params: Parameters containing repo_full_name and time_window_days
        db: Database session

    Returns:
        Health facts
    """
    repo_full_name = params.get("repo_full_name")
    time_window_days = params.get("time_window_days", 30)
    
    # Generate cache key
    cache_key = cache_manager.get_health_facts_key(repo_full_name, time_window_days)
    
    # Check cache
    cached_facts = cache_manager.get(cache_key)
    if cached_facts:
        return cached_facts
    
    # Extract facts
    extractor = create_health_facts_extractor(db)
    facts = extractor.extract_facts(repo_full_name, time_window_days)
    
    # Cache the result
    cache_manager.set(cache_key, facts, cache_manager.ai_reports_ttl)
    
    return facts


def _extract_newcomer_facts(params: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Extract newcomer facts.

    Args:
        params: Parameters containing domain, stack, time_per_week, keywords, top_n
        db: Database session

    Returns:
        Newcomer facts
    """
    domain = params.get("domain")
    stack = params.get("stack")
    time_per_week = params.get("time_per_week")
    keywords = params.get("keywords", "")
    top_n = params.get("top_n", 3)
    
    # Generate cache key
    cache_key = cache_manager.get_newcomer_facts_key(domain, stack, time_per_week, keywords)
    
    # Check cache
    cached_facts = cache_manager.get(cache_key)
    if cached_facts:
        return cached_facts
    
    # Extract facts
    extractor = create_newcomer_facts_extractor(db)
    facts = extractor.extract_facts(domain, stack, time_per_week, keywords, top_n)
    
    # Cache the result
    cache_manager.set(cache_key, facts, cache_manager.ai_reports_ttl)
    
    return facts


def _extract_trend_facts(params: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Extract trend facts.

    Args:
        params: Parameters containing repo_full_name, time_window_days, metrics
        db: Database session

    Returns:
        Trend facts
    """
    repo_full_name = params.get("repo_full_name")
    time_window_days = params.get("time_window_days", 180)
    metrics = params.get("metrics", ["activity", "first_response", "bus_factor", "scorecard"])
    
    # Generate cache key
    cache_key = cache_manager.get_trend_facts_key(repo_full_name, time_window_days, metrics)
    
    # Check cache
    cached_facts = cache_manager.get(cache_key)
    if cached_facts:
        return cached_facts
    
    # Extract facts
    extractor = create_trend_facts_extractor(db)
    facts = extractor.extract_facts(repo_full_name, time_window_days, metrics)
    
    # Cache the result
    cache_manager.set(cache_key, facts, cache_manager.ai_reports_ttl)
    
    return facts


def _load_prompt_template(module: str) -> str:
    """Load prompt template for a module.

    Args:
        module: Report module

    Returns:
        Prompt template
    """
    try:
        with open(f"app/services/ai_service/templates/{module}_prompt.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Return default prompt
        return f"Generate a comprehensive {module} report based on the provided facts."


@router.post("/health", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def generate_health_report(request: HealthReportRequest, db: Session = Depends(get_db)) -> ReportResponse:
    """Generate health report.

    Args:
        request: Health report request
        db: Database session

    Returns:
        Health report response
    """
    params = request.dict()
    result = generate_report("health", params, db)
    return ReportResponse(**result)


@router.post("/newcomer", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def generate_newcomer_report(request: NewcomerReportRequest, db: Session = Depends(get_db)) -> ReportResponse:
    """Generate newcomer report.

    Args:
        request: Newcomer report request
        db: Database session

    Returns:
        Newcomer report response
    """
    params = request.dict()
    result = generate_report("newcomer", params, db)
    return ReportResponse(**result)


@router.post("/trend", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def generate_trend_report(request: TrendReportRequest, db: Session = Depends(get_db)) -> ReportResponse:
    """Generate trend report.

    Args:
        request: Trend report request
        db: Database session

    Returns:
        Trend report response
    """
    params = request.dict()
    result = generate_report("trend", params, db)
    return ReportResponse(**result)


@router.post("/clear-cache", status_code=status.HTTP_200_OK)
def clear_cache() -> Dict[str, Any]:
    """Clear AI service cache.

    Returns:
        Cache clearing result
    """
    cache_manager.clear()
    return {"message": "Cache cleared successfully"}


@router.get("/cache-stats", status_code=status.HTTP_200_OK)
def get_cache_stats() -> Dict[str, Any]:
    """Get AI service cache statistics.

    Returns:
        Cache statistics
    """
    return cache_manager.get_cache_stats()
