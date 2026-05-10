from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.schemas.session import KIBotSession, ReportState
from backend.services.report_generator import generate_report_markdown
from backend.services.session_store import SessionStore


router = APIRouter(prefix="/api/report", tags=["report"])


class ReportGenerateRequest(BaseModel):
    session_id: str


def get_session_store() -> SessionStore:
    return SessionStore()


@router.post("/generate", response_model=ReportState)
def generate_report(
    request: ReportGenerateRequest,
    session_store: SessionStore = Depends(get_session_store),
) -> ReportState:
    session = _load_session(request.session_id, session_store)
    session.report.markdown = generate_report_markdown(session)
    session.report.updated_at = _utc_now()
    session_store.save_session(session)
    return session.report


@router.get("", response_model=ReportState)
def get_report(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> ReportState:
    session = _load_session(session_id, session_store)
    return session.report


def _load_session(session_id: str | None, session_store: SessionStore) -> KIBotSession:
    if not session_id:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    try:
        return session_store.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
