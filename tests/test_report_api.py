import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class ReportApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

        from backend.services.session_store import SessionStore

        self.store = SessionStore(storage_dir=Path(self.temp_dir.name))
        self.app = None
        self.report_dependency = None

    def tearDown(self) -> None:
        if self.app is not None and self.report_dependency is not None:
            self.app.dependency_overrides.pop(self.report_dependency, None)
        self.temp_dir.cleanup()

    def client(self):
        import backend.api.report as report_api

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(report_api.router)
        app.dependency_overrides[report_api.get_session_store] = lambda: self.store
        self.app = app
        self.report_dependency = report_api.get_session_store
        return TestClient(app)

    def test_generate_report_persists_markdown_and_timestamp(self) -> None:
        client = self.client()
        session = self.store.create_session()
        session.selected_textbooks = ["bio-1"]
        session.graph_nodes = [{"id": "n1", "name": "ATP"}]
        session.integration_decisions = [{"decision_id": "d1", "summary": "Keep ATP."}]
        self.store.save_session(session)

        response = client.post(
            "/api/report/generate",
            json={"session_id": session.session_id},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("## 整合概览", payload["markdown"])
        self.assertIn("已选择教材：1 本", payload["markdown"])
        self.assertIsNotNone(payload["updated_at"])

        saved = self.store.get_session(session.session_id)
        self.assertEqual(saved.report.markdown, payload["markdown"])
        self.assertEqual(saved.report.updated_at, payload["updated_at"])

    def test_get_report_returns_saved_report_state(self) -> None:
        client = self.client()
        session = self.store.create_session()
        session.report.markdown = "# Saved Report"
        session.report.updated_at = "2026-05-10T12:00:00Z"
        self.store.save_session(session)

        response = client.get(f"/api/report?session_id={session.session_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "markdown": "# Saved Report",
                "updated_at": "2026-05-10T12:00:00Z",
            },
        )

    def test_report_endpoints_validate_session_id(self) -> None:
        client = self.client()

        invalid_generate = client.post("/api/report/generate", json={"session_id": "bad"})
        self.assertEqual(invalid_generate.status_code, 400)

        unknown_get = client.get(f"/api/report?session_id={uuid4()}")
        self.assertEqual(unknown_get.status_code, 404)


if __name__ == "__main__":
    unittest.main()
