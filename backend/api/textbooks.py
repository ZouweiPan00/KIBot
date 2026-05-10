from pathlib import Path, PurePosixPath
import re
from typing import Any, Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from backend.schemas.session import KIBotSession
from backend.schemas.textbook import ParsedTextbook
from backend.services.session_store import SessionStore
from backend.services.textbook_parser import get_file_type, parse_textbook


router = APIRouter(prefix="/api/textbooks", tags=["textbooks"])


def get_session_store() -> SessionStore:
    return SessionStore()


@router.post("/upload", response_model=ParsedTextbook)
async def upload_textbook(
    file: Annotated[UploadFile, File()],
    form_session_id: Annotated[str | None, Form(alias="session_id")] = None,
    query_session_id: Annotated[str | None, Query(alias="session_id")] = None,
    session_store: SessionStore = Depends(get_session_store),
) -> ParsedTextbook:
    session_id = form_session_id or query_session_id
    session = _load_session(session_id, session_store)

    safe_filename = _safe_filename(file.filename)
    try:
        get_file_type(safe_filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Unsupported textbook file type",
        ) from exc

    upload_dir = _session_upload_dir(session_store, session.session_id)
    upload_path = _safe_upload_path(upload_dir, safe_filename)
    upload_path.write_bytes(await file.read())

    try:
        parsed = parse_textbook(upload_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    parsed_payload = parsed.model_dump(mode="json")
    session.textbooks.append(parsed_payload)
    session.chapters.extend(_session_chapter_payloads(parsed))
    session_store.save_session(session)

    return parsed


@router.get("")
def list_textbooks(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> list[Any]:
    session = _load_session(session_id, session_store)
    return session.textbooks


@router.post("/{textbook_id}/select", response_model=KIBotSession)
def select_textbook(
    textbook_id: str,
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> KIBotSession:
    session = _load_session(session_id, session_store)
    _ensure_textbook_exists(session, textbook_id)

    if textbook_id not in session.selected_textbooks:
        session.selected_textbooks.append(textbook_id)
        session_store.save_session(session)

    return session


@router.delete("/{textbook_id}", response_model=KIBotSession)
def delete_textbook(
    textbook_id: str,
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> KIBotSession:
    session = _load_session(session_id, session_store)
    _ensure_textbook_exists(session, textbook_id)

    session.textbooks = [
        textbook
        for textbook in session.textbooks
        if _textbook_id(textbook) != textbook_id
    ]
    session.selected_textbooks = [
        selected_id
        for selected_id in session.selected_textbooks
        if selected_id != textbook_id
    ]
    session.chapters = [
        chapter
        for chapter in session.chapters
        if _chapter_textbook_id(chapter) != textbook_id
    ]
    session_store.save_session(session)

    return session


def _load_session(session_id: str | None, session_store: SessionStore) -> KIBotSession:
    if not session_id:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    try:
        return session_store.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


def _safe_filename(filename: str | None) -> str:
    raw_name = (filename or "textbook").replace("\\", "/")
    name = PurePosixPath(raw_name).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip()
    name = name.strip(".")
    return name or "textbook"


def _session_upload_dir(session_store: SessionStore, session_id: str) -> Path:
    upload_dir = session_store.storage_dir / session_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir.resolve()


def _safe_upload_path(upload_dir: Path, filename: str) -> Path:
    upload_path = (upload_dir / filename).resolve()
    try:
        upload_path.relative_to(upload_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid filename") from exc
    return upload_path


def _session_chapter_payloads(parsed: ParsedTextbook) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for chapter in parsed.chapters:
        payload = chapter.model_dump(mode="json")
        payload["textbook_id"] = parsed.textbook_id
        payloads.append(payload)
    return payloads


def _ensure_textbook_exists(session: KIBotSession, textbook_id: str) -> None:
    if any(_textbook_id(textbook) == textbook_id for textbook in session.textbooks):
        return
    raise HTTPException(status_code=404, detail="Textbook not found")


def _textbook_id(textbook: Any) -> str | None:
    if isinstance(textbook, dict):
        value = textbook.get("textbook_id")
        return value if isinstance(value, str) else None
    value = getattr(textbook, "textbook_id", None)
    return value if isinstance(value, str) else None


def _chapter_textbook_id(chapter: Any) -> str | None:
    if isinstance(chapter, dict):
        value = chapter.get("textbook_id")
        return value if isinstance(value, str) else None
    value = getattr(chapter, "textbook_id", None)
    return value if isinstance(value, str) else None
