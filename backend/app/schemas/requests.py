from __future__ import annotations
from datetime import date
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class BatchTrendRequest(BaseModel):
    repos: list[str] = Field(..., description="repo list")
    metric: str = Field(..., description="metric name")
    range: str = Field("30d", description="time range like 30d")


class HealthIngestRequest(BaseModel):
    repo_full_name: str = Field(..., description="owner/repo")
    dt: date = Field(..., description="snapshot date")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="flattened metrics map")
    governance_files: Dict[str, Any] = Field(default_factory=dict, description="governance files presence map")
    scorecard_checks: Dict[str, Any] = Field(default_factory=dict, description="Scorecard check detail")
    security_defaulted: bool = Field(False, description="whether a default security score is used")
    raw_payloads: Dict[str, Any] = Field(default_factory=dict, description="optional raw payloads for traceability")


class NewcomerPlanRequest(BaseModel):
    domains: list[str] = Field(default_factory=list, description="user selected domains")
    stacks: list[str] = Field(default_factory=list, description="user selected stacks")
    # Legacy scalar fields remain accepted for older clients.
    domain: Optional[str] = Field(None, description="legacy single selected domain")
    stack: Optional[str] = Field(None, description="legacy single selected stack")
    time_per_week: str = Field(..., description="time availability per week")
    keywords: str = Field("", description="additional keywords for matching")


class TrendSeriesRequest(BaseModel):
    repo: str = Field(..., description="仓库名称，格式：owner/repo")
    start: Optional[str] = Field(None, description="开始日期，格式：YYYY-MM-DD")
    end: Optional[str] = Field(None, description="结束日期，格式：YYYY-MM-DD")
    metrics: list[str] = Field(..., description="指标列表")


class TrendDerivedRequest(BaseModel):
    repo: str = Field(..., description="仓库名称，格式：owner/repo")
    metric: str = Field(..., description="指标名称")
    window: int = Field(30, description="时间窗口，默认 30 天")


class TrendReportRequest(BaseModel):
    repo: str = Field(..., description="仓库名称，格式：owner/repo")
    time_window: Optional[int | str] = Field(None, description="时间窗口（天），支持 all 表示全量")
    trend_conclusions: Optional[Dict[str, str]] = Field(None, description="趋势结论")
    key_metrics: Optional[Dict[str, Any]] = Field(None, description="关键指标数据")
