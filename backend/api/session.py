from fastapi import APIRouter, Depends, HTTPException

from backend.schemas.session import KIBotSession
from backend.services.session_store import SessionStore


router = APIRouter(prefix="/api/session", tags=["session"])


def get_session_store() -> SessionStore:
    return SessionStore()


@router.post("", response_model=KIBotSession)
def create_session(
    session_store: SessionStore = Depends(get_session_store),
) -> KIBotSession:
    return session_store.create_session()


@router.get("/{session_id}", response_model=KIBotSession)
def get_session(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> KIBotSession:
    try:
        return session_store.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.post("/{session_id}/reset", response_model=KIBotSession)
def reset_session(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> KIBotSession:
    try:
        return session_store.reset_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
