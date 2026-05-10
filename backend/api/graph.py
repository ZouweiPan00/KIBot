from fastapi import APIRouter, Depends, HTTPException

from backend.schemas.graph import GraphBuildRequest, GraphResponse, KnowledgeGraph
from backend.schemas.session import KIBotSession, ReportState
from backend.core.config import settings
from backend.services.graph_builder import build_knowledge_graph
from backend.services.llm_client import LLMClient
from backend.services.session_store import SessionStore


router = APIRouter(prefix="/api/graph", tags=["graph"])


def get_session_store() -> SessionStore:
    return SessionStore()


@router.post("/build", response_model=GraphResponse)
def build_graph(
    request: GraphBuildRequest,
    session_store: SessionStore = Depends(get_session_store),
) -> KnowledgeGraph:
    session = _load_session(request.session_id, session_store)
    llm_client = _graph_llm_client(request.use_ai)
    try:
        graph = build_knowledge_graph(
            session.chunks,
            selected_textbook_ids=session.selected_textbooks,
            llm_client=llm_client,
            use_ai=llm_client is not None,
        )
    finally:
        if llm_client is not None:
            _record_token_usage(session, llm_client)
            llm_client.close()
    session.graph_nodes = [node.model_dump(mode="json") for node in graph.nodes]
    session.graph_edges = [edge.model_dump(mode="json") for edge in graph.edges]
    session.integration_decisions = []
    session.report = ReportState()
    session_store.save_session(session)
    return graph


@router.get("", response_model=GraphResponse)
def get_graph(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> GraphResponse:
    session = _load_session(session_id, session_store)
    return GraphResponse(nodes=session.graph_nodes, edges=session.graph_edges)


def _load_session(session_id: str | None, session_store: SessionStore) -> KIBotSession:
    if not session_id:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    try:
        return session_store.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


class _TokenTrackingGraphClient:
    def __init__(self) -> None:
        self._client = LLMClient()
        self.token_usage = None

    def chat(self, messages):
        response = self._client.chat(messages)
        self.token_usage = response.token_usage
        return response

    def close(self) -> None:
        self._client.close()


def _graph_llm_client(use_ai: bool) -> _TokenTrackingGraphClient | None:
    if not use_ai or not settings.openai_api_key:
        return None
    return _TokenTrackingGraphClient()


def _record_token_usage(session: KIBotSession, llm_client: _TokenTrackingGraphClient) -> None:
    usage = llm_client.token_usage
    if usage is None:
        return
    session.token_usage.calls += usage.calls
    session.token_usage.input_tokens += usage.input_tokens
    session.token_usage.output_tokens += usage.output_tokens
    session.token_usage.total_tokens += usage.total_tokens
