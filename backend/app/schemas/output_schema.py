from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

Status = Literal["green", "yellow", "red"]

class EvidenceCard(BaseModel):
    title: str
    detail: str
    metric: Optional[str] = None
    window_days: Optional[int] = None
    source: Optional[str] = "opendigger"
    refs: list[str] = Field(default_factory=list)

class Chart(BaseModel):
    chart_type: str
    title: str
    data: Any

class ActionItem(BaseModel):
    action: str
    priority: Literal["P0","P1","P2"] = "P1"
    owner: Optional[str] = None
    eta: Optional[str] = None

class Summary(BaseModel):
    headline: str
    status: Status = "yellow"
    key_points: list[str] = Field(default_factory=list)
    confidence: float = 0.5

class OutputSchema(BaseModel):
    request_id: str
    timestamp: str
    scenario: str
    task: str
    input: dict
    summary: Summary
    evidence_cards: list[EvidenceCard] = Field(default_factory=list)
    charts: list[Chart] = Field(default_factory=list)
    actions: list[ActionItem] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    debug: dict = Field(default_factory=dict)
