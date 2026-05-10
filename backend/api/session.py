from fastapi import APIRouter, HTTPException

from backend.schemas.session import KIBotSession
from backend.services.session_store import SessionStore


router = APIRouter(prefix="/api/session", tags=["session"])
session_store = SessionStore()


@router.post("", response_model=KIBotSession)
def create_session() -> KIBotSession:
    return session_store.create_session()


@router.get("/{session_id}", response_model=KIBotSession)
def get_session(session_id: str) -> KIBotSession:
    try:
        return session_store.get_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.post("/{session_id}/reset", response_model=KIBotSession)
def reset_session(session_id: str) -> KIBotSession:
    try:
        return session_store.reset_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
