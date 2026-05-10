from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.schemas.integration import (
    IntegrationDecisionsResponse,
    IntegrationRunRequest,
    IntegrationRunResponse,
    IntegrationStatsResponse,
    IntegrationUpdateRequest,
    SankeyData,
)
from backend.schemas.session import KIBotSession
from backend.services.integration_engine import (
    build_sankey,
    compute_stats,
    run_integration,
    update_decision,
)
from backend.services.session_store import SessionStore


router = APIRouter(prefix="/api/integration", tags=["integration"])


def get_session_store() -> SessionStore:
    return SessionStore()


@router.post("/run", response_model=IntegrationRunResponse)
def run_integration_api(
    request: IntegrationRunRequest,
    session_store: SessionStore = Depends(get_session_store),
) -> dict[str, Any]:
    session = _load_session(request.session_id, session_store)
    try:
        result = run_integration(session)
        session.integration_decisions = result.decisions
        session_store.save_session(session)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Integration failed. Please retry with fewer selected textbooks.",
        ) from exc
    return {
        "session_id": session.session_id,
        "decisions": result.decisions,
        "stats": result.stats,
        "sankey": result.sankey,
    }


@router.get("/decisions", response_model=IntegrationDecisionsResponse)
def get_integration_decisions(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> dict[str, Any]:
    session = _load_session(session_id, session_store)
    return {"session_id": session.session_id, "decisions": session.integration_decisions}


@router.post("/decisions/{decision_id}")
def update_integration_decision(
    decision_id: str,
    request: IntegrationUpdateRequest,
    session_store: SessionStore = Depends(get_session_store),
) -> dict[str, Any]:
    session = _load_session(request.session_id, session_store)
    updated = update_decision(
        session.integration_decisions,
        decision_id,
        action=request.action,
        teacher_note=request.teacher_note,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Decision not found")
    session_store.save_session(session)
    return next(
        decision
        for decision in session.integration_decisions
        if isinstance(decision, dict) and decision.get("decision_id") == decision_id
    )


@router.get("/stats", response_model=IntegrationStatsResponse)
def get_integration_stats(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> dict[str, Any]:
    session = _load_session(session_id, session_store)
    return {
        "session_id": session.session_id,
        "stats": compute_stats(session, session.integration_decisions),
    }


@router.get("/sankey", response_model=SankeyData)
def get_integration_sankey(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> dict[str, Any]:
    session = _load_session(session_id, session_store)
    return build_sankey(session.integration_decisions)


def _load_session(session_id: str | None, session_store: SessionStore) -> KIBotSession:
    if not session_id:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    try:
        return session_store.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
