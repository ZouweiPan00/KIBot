from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from backend.schemas.session import KIBotSession
from backend.services.llm_client import LLMClient
from backend.services.retriever import answer_query
from backend.services.session_store import SessionStore


router = APIRouter(prefix="/api/rag", tags=["rag"])


class RAGQueryRequest(BaseModel):
    session_id: str
    question: str | None = Field(default=None)
    query: str | None = Field(default=None)

    @model_validator(mode="after")
    def validate_question_text(self) -> "RAGQueryRequest":
        if not self.question_text:
            raise ValueError("question or query is required")
        return self

    @property
    def question_text(self) -> str:
        return (self.question or self.query or "").strip()


def get_session_store() -> SessionStore:
    return SessionStore()


def get_llm_client() -> LLMClient | None:
    return LLMClient()


@router.get("/status")
def rag_status(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> dict[str, Any]:
    session = _load_session(session_id, session_store)
    return {
        "session_id": session.session_id,
        "ready": bool(session.chunks),
        "chunk_count": len(session.chunks),
        "graph_node_count": len(session.graph_nodes),
    }


@router.post("/query")
def query_rag(
    request: RAGQueryRequest,
    session_store: SessionStore = Depends(get_session_store),
    llm_client: LLMClient | None = Depends(get_llm_client),
) -> dict[str, Any]:
    session = _load_session(request.session_id, session_store)
    return answer_query(session, request.question_text, llm_client=llm_client)


def _load_session(session_id: str | None, session_store: SessionStore) -> KIBotSession:
    if not session_id:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    try:
        return session_store.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
