from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    name: str
    definition: str
    category: str = "concept"
    textbook_id: str
    textbook_title: str
    chapter: str
    page: int = 1
    frequency: int = 1
    importance: float = 1.0
    status: str = "active"


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation_type: str = "co_occurs"
    description: str
    confidence: float = Field(ge=0.0, le=1.0)


class KnowledgeGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class GraphBuildRequest(BaseModel):
    session_id: str


class GraphResponse(KnowledgeGraph):
    pass
