from fastapi import APIRouter, Depends, HTTPException

from backend.schemas.graph import GraphBuildRequest, GraphResponse, KnowledgeGraph
from backend.schemas.session import KIBotSession
from backend.services.graph_builder import build_knowledge_graph
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
    graph = build_knowledge_graph(
        session.chunks,
        selected_textbook_ids=session.selected_textbooks,
    )
    session.graph_nodes = [node.model_dump(mode="json") for node in graph.nodes]
    session.graph_edges = [edge.model_dump(mode="json") for edge in graph.edges]
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
