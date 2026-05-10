import json
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from backend.core.paths import SESSION_STORAGE_DIR
from backend.schemas.session import KIBotSession


class SessionStore:
    def __init__(self, storage_dir: str | Path | None = None) -> None:
        if storage_dir is None:
            self.storage_dir = SESSION_STORAGE_DIR.resolve()
        else:
            self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self) -> KIBotSession:
        session = KIBotSession(session_id=str(uuid4()))
        return self.save_session(session)

    def get_session(self, session_id: str) -> KIBotSession:
        session_file = self._session_file(session_id)
        if not session_file.exists():
            raise FileNotFoundError(session_file)

        return KIBotSession.model_validate_json(
            session_file.read_text(encoding="utf-8")
        )

    def save_session(self, session: KIBotSession) -> KIBotSession:
        session_file = self._session_file(session.session_id)
        session_file.parent.mkdir(parents=True, exist_ok=True)

        payload = json.dumps(
            session.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        temp_file = session_file.with_suffix(".json.tmp")
        temp_file.write_text(f"{payload}\n", encoding="utf-8")
        temp_file.replace(session_file)
        return session

    def reset_session(self, session_id: str) -> KIBotSession:
        self.get_session(session_id)
        session = KIBotSession(session_id=session_id)
        return self.save_session(session)

    def delete_session(self, session_id: str) -> None:
        session_file = self._session_file(session_id)
        if not session_file.exists():
            raise FileNotFoundError(session_file)
        shutil.rmtree(session_file.parent)

    def _session_file(self, session_id: str) -> Path:
        safe_session_id = self._validate_session_id(session_id)
        session_file = self.storage_dir / safe_session_id / "session.json"

        try:
            session_file.resolve().relative_to(self.storage_dir)
        except ValueError as exc:
            raise ValueError("Session ID escapes storage directory") from exc

        return session_file

    def _validate_session_id(self, session_id: str) -> str:
        try:
            parsed = UUID(session_id)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("Invalid session ID") from exc

        normalized = str(parsed)
        if session_id != normalized:
            raise ValueError("Invalid session ID")

        return normalized
