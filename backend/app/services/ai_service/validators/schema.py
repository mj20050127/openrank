"""Report JSON schema definitions using Pydantic."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """Evidence for a report section."""
    key: str = Field(..., description="Metric key from facts")
    value: float = Field(..., description="Value from facts")
    dt: str = Field(..., description="Date of the value")


class ReportSection(BaseModel):
    """Section of a report."""
    title: str = Field(..., description="Section title")
    content_md: str = Field(..., description="Section content in Markdown")
    evidence: List[Evidence] = Field(default_factory=list, description="Evidence for the section")


class ActionItem(BaseModel):
    """Action item in a report."""
    title: str = Field(..., description="Action title")
    steps: List[str] = Field(..., description="Steps to complete the action")
    priority: str = Field(..., description="Priority (P0, P1, P2)")


class ReportJSON(BaseModel):
    """Structured report JSON schema."""
    module: str = Field(..., description="Report module (health, newcomer, trend)")
    repo: Optional[str] = Field(None, description="Repository full name")
    time_window_days: int = Field(..., description="Time window in days")
    used_dt: Optional[str] = Field(None, description="Latest date used in the report")
    summary_bullets: List[str] = Field(default_factory=list, description="Summary bullets")
    sections: List[ReportSection] = Field(default_factory=list, description="Report sections")
    actions: List[ActionItem] = Field(default_factory=list, description="Action items")
    monitor: List[str] = Field(default_factory=list, description="Metrics to monitor")
    warnings: List[str] = Field(default_factory=list, description="Data quality warnings")
    error: Optional[str] = Field(None, description="Error message if report generation failed")


class HealthReportJSON(ReportJSON):
    """Health report specific JSON schema."""
    module: str = Field("health", description="Report module")
    dimensions: Optional[Dict[str, Any]] = Field(None, description="Dimension scores")


class NewcomerReportJSON(ReportJSON):
    """Newcomer report specific JSON schema."""
    module: str = Field("newcomer", description="Report module")
    top_repos: Optional[List[Dict[str, Any]]] = Field(None, description="Top recommended repositories")


class TrendReportJSON(ReportJSON):
    """Trend report specific JSON schema."""
    module: str = Field("trend", description="Report module")
    trends: Optional[Dict[str, Any]] = Field(None, description="Trend analysis results")
    anomalies: Optional[List[Dict[str, Any]]] = Field(None, description="Detected anomalies")


class ReportResponse(BaseModel):
    """API response for report generation."""
    report_json: Dict[str, Any] = Field(..., description="Generated report in JSON format")
    report_markdown: str = Field(..., description="Generated report in Markdown format")
    meta: Dict[str, Any] = Field(..., description="Meta information about the report")


class HealthReportRequest(BaseModel):
    """Request for health report generation."""
    repo_full_name: str = Field(..., description="Repository full name (owner/repo)")
    time_window_days: int = Field(default=30, description="Time window in days")


class NewcomerReportRequest(BaseModel):
    """Request for newcomer report generation."""
    domain: str = Field(..., description="Interest domain (e.g., frontend, backend, ai_ml)")
    stack: str = Field(..., description="Technology stack (e.g., javascript, python, go)")
    time_per_week: str = Field(..., description="Time available per week (e.g., 1-2h, 3-5h)")
    keywords: str = Field(default="", description="Additional keywords for filtering")
    top_n: int = Field(default=3, description="Number of top repositories to return")


class TrendReportRequest(BaseModel):
    """Request for trend report generation."""
    repo_full_name: str = Field(..., description="Repository full name (owner/repo)")
    time_window_days: int = Field(default=180, description="Time window in days")
    metrics: List[str] = Field(default_factory=lambda: ["activity", "first_response", "bus_factor", "scorecard"], description="Metrics to analyze")


# Fact schemas
class HealthFacts(BaseModel):
    """Health facts schema."""
    repo_full_name: str
    time_window_days: int
    used_dt: Optional[str]
    score_health: Optional[float]
    dimensions: Dict[str, Any]
    metrics: Dict[str, Any]
    data_quality: Dict[str, Any]


class NewcomerFacts(BaseModel):
    """Newcomer facts schema."""
    input: Dict[str, str]
    top_repos: List[Dict[str, Any]]
    data_quality: Dict[str, Any]


class TrendFacts(BaseModel):
    """Trend facts schema."""
    repo_full_name: str
    time_window_days: int
    metrics: List[str]
    used_dt: Optional[str]
    trends: Dict[str, Any]
    anomalies: List[Dict[str, Any]]
    data_quality: Dict[str, Any]
