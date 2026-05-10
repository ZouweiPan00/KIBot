import sys
import tempfile
import unittest
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class SessionApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

        from backend.services.session_store import SessionStore
        import backend.api.session as session_api

        session_api.session_store = SessionStore(storage_dir=Path(self.temp_dir.name))

        from app import app
        from fastapi.testclient import TestClient

        self.session_api = session_api
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_post_session_creates_retrievable_session(self) -> None:
        create_response = self.client.post("/api/session")

        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()
        UUID(created["session_id"])
        self.assertEqual(created["messages"], [])
        self.assertEqual(created["memory_summary"], "")
        self.assertEqual(created["token_usage"]["total_tokens"], 0)
        self.assertEqual(created["report"]["markdown"], "")

        get_response = self.client.get(f"/api/session/{created['session_id']}")

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json(), created)

    def test_get_unknown_session_returns_404(self) -> None:
        response = self.client.get("/api/session/missing-session")

        self.assertEqual(response.status_code, 404)

    def test_reset_session_clears_existing_session_state(self) -> None:
        created = self.client.post("/api/session").json()
        session = self.session_api.session_store.get_session(created["session_id"])
        session.messages.append({"role": "user", "content": "Keep this briefly"})
        session.memory_summary = "Temporary context"
        session.token_usage.calls = 2
        self.session_api.session_store.save_session(session)

        response = self.client.post(f"/api/session/{created['session_id']}/reset")

        self.assertEqual(response.status_code, 200)
        reset = response.json()
        self.assertEqual(reset["session_id"], created["session_id"])
        self.assertEqual(reset["messages"], [])
        self.assertEqual(reset["memory_summary"], "")
        self.assertEqual(reset["token_usage"]["calls"], 0)


if __name__ == "__main__":
    unittest.main()
