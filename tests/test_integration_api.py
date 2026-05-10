import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class IntegrationApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

        from backend.services.session_store import SessionStore

        self.store = SessionStore(storage_dir=Path(self.temp_dir.name))
        self.app = None
        self.integration_dependency = None

    def tearDown(self) -> None:
        if self.app is not None and self.integration_dependency is not None:
            self.app.dependency_overrides.pop(self.integration_dependency, None)
        self.temp_dir.cleanup()

    def client(self):
        import backend.api.integration as integration_api

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(integration_api.router)
        app.dependency_overrides[integration_api.get_session_store] = lambda: self.store
        self.app = app
        self.integration_dependency = integration_api.get_session_store
        return TestClient(app)

    def session_with_integration_inputs(self):
        session = self.store.create_session()
        session.selected_textbooks.extend(["pathology", "immunology"])
        session.textbooks.extend(
            [
                {"textbook_id": "pathology", "title": "病理学", "total_chars": 1200},
                {"textbook_id": "immunology", "title": "免疫学", "total_chars": 800},
            ]
        )
        session.graph_nodes.extend(
            [
                {
                    "id": "pathology:inflammation",
                    "name": "炎症",
                    "textbook_id": "pathology",
                    "textbook_title": "病理学",
                    "chapter": "急性炎症",
                    "definition": "炎症 includes vascular response.",
                },
                {
                    "id": "immunology:inflammatory-response",
                    "name": "炎症反应",
                    "textbook_id": "immunology",
                    "textbook_title": "免疫学",
                    "chapter": "固有免疫",
                    "definition": "炎症反应 includes immune cell recruitment.",
                },
            ]
        )
        return self.store.save_session(session)

    def test_run_persists_decisions_stats_and_sankey(self) -> None:
        client = self.client()
        session = self.session_with_integration_inputs()

        response = client.post(
            "/api/integration/run",
            json={"session_id": session.session_id},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session_id"], session.session_id)
        self.assertGreaterEqual(len(payload["decisions"]), 1)
        self.assertLessEqual(payload["stats"]["ratio"], 0.30)
        self.assertIn("nodes", payload["sankey"])
        self.assertIn("links", payload["sankey"])

        saved = self.store.get_session(session.session_id)
        self.assertEqual(saved.integration_decisions, payload["decisions"])

    def test_get_update_stats_and_sankey_endpoints_use_saved_decisions(self) -> None:
        client = self.client()
        session = self.session_with_integration_inputs()
        run_payload = client.post(
            "/api/integration/run",
            json={"session_id": session.session_id},
        ).json()
        decision_id = run_payload["decisions"][0]["decision_id"]

        update = client.post(
            f"/api/integration/decisions/{decision_id}",
            json={
                "session_id": session.session_id,
                "action": "keep",
                "teacher_note": "Keep separate in lecture.",
            },
        )
        decisions = client.get(
            f"/api/integration/decisions?session_id={session.session_id}"
        )
        stats = client.get(f"/api/integration/stats?session_id={session.session_id}")
        sankey = client.get(f"/api/integration/sankey?session_id={session.session_id}")

        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["action"], "keep")
        self.assertEqual(update.json()["teacher_note"], "Keep separate in lecture.")
        self.assertEqual(decisions.status_code, 200)
        self.assertEqual(decisions.json()["decisions"][0]["action"], "keep")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.json()["stats"]["original_chars"], 2000)
        self.assertEqual(sankey.status_code, 200)
        self.assertIn(
            {"source": "病理学-炎症", "target": "整合-炎症", "value": 1},
            sankey.json()["links"],
        )

        saved = self.store.get_session(session.session_id)
        self.assertEqual(saved.integration_decisions[0]["action"], "keep")
        self.assertEqual(
            saved.integration_decisions[0]["teacher_note"],
            "Keep separate in lecture.",
        )

    def test_integration_endpoints_validate_session_and_decision_ids(self) -> None:
        client = self.client()
        session = self.store.create_session()

        invalid = client.post("/api/integration/run", json={"session_id": "bad"})
        unknown = client.get(f"/api/integration/decisions?session_id={uuid4()}")
        missing_decision = client.post(
            "/api/integration/decisions/missing",
            json={"session_id": session.session_id, "action": "merge"},
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(missing_decision.status_code, 404)


if __name__ == "__main__":
    unittest.main()
