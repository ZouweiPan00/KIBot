from typing import Any, Literal

from pydantic import BaseModel, Field


IntegrationAction = Literal["merge", "keep", "remove", "split"]


class IntegrationRunRequest(BaseModel):
    session_id: str


class IntegrationUpdateRequest(BaseModel):
    session_id: str
    action: IntegrationAction
    teacher_note: str = ""


class IntegrationDecision(BaseModel):
    decision_id: str
    action: IntegrationAction
    concept_name: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    compact_note: str = ""
    teacher_note: str = ""


class IntegrationStats(BaseModel):
    original_chars: int = 0
    compressed_chars: int = 0
    ratio: float = 0.0


class SankeyNode(BaseModel):
    name: str


class SankeyLink(BaseModel):
    source: str
    target: str
    value: int = 1


class SankeyData(BaseModel):
    nodes: list[SankeyNode] = Field(default_factory=list)
    links: list[SankeyLink] = Field(default_factory=list)


class IntegrationRunResponse(BaseModel):
    session_id: str
    decisions: list[IntegrationDecision]
    stats: IntegrationStats
    sankey: SankeyData


class IntegrationDecisionsResponse(BaseModel):
    session_id: str
    decisions: list[IntegrationDecision]


class IntegrationStatsResponse(BaseModel):
    session_id: str
    stats: IntegrationStats
