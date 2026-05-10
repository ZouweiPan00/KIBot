from typing import Any

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ReportState(BaseModel):
    markdown: str = ""
    updated_at: str | None = None


class KIBotSession(BaseModel):
    session_id: str
    selected_textbooks: list[Any] = Field(default_factory=list)
    textbooks: list[Any] = Field(default_factory=list)
    chapters: list[Any] = Field(default_factory=list)
    chunks: list[Any] = Field(default_factory=list)
    graph_nodes: list[Any] = Field(default_factory=list)
    graph_edges: list[Any] = Field(default_factory=list)
    integration_decisions: list[Any] = Field(default_factory=list)
    messages: list[Any] = Field(default_factory=list)
    memory_summary: str = ""
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    report: ReportState = Field(default_factory=ReportState)
