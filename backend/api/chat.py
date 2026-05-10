from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.schemas.session import KIBotSession
from backend.services.dialogue import DialogueService
from backend.services.session_store import SessionStore


router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        return value


class ChatMessageResponse(BaseModel):
    assistant_message: str
    parsed_intent: dict[str, Any]
    state_summary: dict[str, Any]


def get_session_store() -> SessionStore:
    return SessionStore()


@router.post("/message", response_model=ChatMessageResponse)
def post_message(
    request: ChatMessageRequest,
    session_store: SessionStore = Depends(get_session_store),
) -> dict[str, Any]:
    session = _load_session(request.session_id, session_store)
    result = DialogueService().handle_message(session, request.message)
    session_store.save_session(session)
    return {
        "assistant_message": result.assistant_message,
        "parsed_intent": result.parsed_intent,
        "state_summary": result.state_summary,
    }


def _load_session(session_id: str | None, session_store: SessionStore) -> KIBotSession:
    if not session_id:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    try:
        return session_store.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
