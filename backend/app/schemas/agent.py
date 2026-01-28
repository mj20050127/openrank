from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional


class Msg(BaseModel):
	role: Literal["system", "user", "assistant"]
	content: str


class Report(BaseModel):
	text: str


class AgentRequest(BaseModel):
	query: str
	selected_repo: Optional[str] = None
	messages: List[Msg] = Field(default_factory=list)
	model: Optional[str] = None
	stream: Optional[bool] = False
	temperature: Optional[float] = 0.2
	max_tokens: Optional[int] = 4096


class AgentResponse(BaseModel):
	report: Report
	tool_results: List[Dict[str, Any]] = Field(default_factory=list)
