import json
from pathlib import Path
from uuid import uuid4

from backend.core.paths import SESSION_STORAGE_DIR
from backend.schemas.session import KIBotSession


class SessionStore:
    def __init__(self, storage_dir: str | Path | None = None) -> None:
        if storage_dir is None:
            self.storage_dir = SESSION_STORAGE_DIR
        else:
            self.storage_dir = Path(storage_dir)
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

    def _session_file(self, session_id: str) -> Path:
        return self.storage_dir / session_id / "session.json"
