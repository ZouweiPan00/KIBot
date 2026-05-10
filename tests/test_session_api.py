import sys
import tempfile
import unittest
from importlib import import_module
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class SessionApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

        from backend.services.session_store import SessionStore

        self.store = SessionStore(storage_dir=Path(self.temp_dir.name))
        self.app = None
        self.get_session_store = None

    def tearDown(self) -> None:
        if self.app is not None and self.get_session_store is not None:
            self.app.dependency_overrides.pop(self.get_session_store, None)
        self.temp_dir.cleanup()

    def client(self):
        import backend.api.session as session_api

        from app import app
        from fastapi.testclient import TestClient

        app.dependency_overrides[session_api.get_session_store] = lambda: self.store
        self.app = app
        self.get_session_store = session_api.get_session_store
        return TestClient(app)

    def test_post_session_creates_retrievable_session(self) -> None:
        client = self.client()

        create_response = client.post("/api/session")

        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()
        UUID(created["session_id"])
        self.assertEqual(created["messages"], [])
        self.assertEqual(created["memory_summary"], "")
        self.assertEqual(created["token_usage"]["total_tokens"], 0)
        self.assertEqual(created["report"]["markdown"], "")

        get_response = client.get(f"/api/session/{created['session_id']}")

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json(), created)

    def test_get_unknown_session_returns_404(self) -> None:
        response = self.client().get(f"/api/session/{uuid4()}")

        self.assertEqual(response.status_code, 404)

    def test_invalid_session_id_returns_400(self) -> None:
        response = self.client().get("/api/session/not-a-uuid")

        self.assertEqual(response.status_code, 400)

    def test_importing_app_does_not_construct_default_session_store(self) -> None:
        sys.modules.pop("app", None)
        sys.modules.pop("backend.api.session", None)

        with patch(
            "backend.services.session_store.SessionStore.__init__",
            side_effect=AssertionError("SessionStore constructed during import"),
        ):
            import_module("app")

    def test_reset_session_clears_existing_session_state(self) -> None:
        client = self.client()
        created = client.post("/api/session").json()
        session = self.store.get_session(created["session_id"])
        session.messages.append({"role": "user", "content": "Keep this briefly"})
        session.memory_summary = "Temporary context"
        session.token_usage.calls = 2
        self.store.save_session(session)

        response = client.post(f"/api/session/{created['session_id']}/reset")

        self.assertEqual(response.status_code, 200)
        reset = response.json()
        self.assertEqual(reset["session_id"], created["session_id"])
        self.assertEqual(reset["messages"], [])
        self.assertEqual(reset["memory_summary"], "")
        self.assertEqual(reset["token_usage"]["calls"], 0)

    def test_delete_session_removes_saved_session(self) -> None:
        client = self.client()
        created = client.post("/api/session").json()

        delete_response = client.delete(f"/api/session/{created['session_id']}")
        get_response = client.get(f"/api/session/{created['session_id']}")
        invalid_delete = client.delete("/api/session/not-a-uuid")

        self.assertEqual(delete_response.status_code, 204)
        self.assertEqual(delete_response.content, b"")
        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(invalid_delete.status_code, 400)


if __name__ == "__main__":
    unittest.main()
