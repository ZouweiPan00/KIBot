import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class AppRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

        from backend.services.session_store import SessionStore

        self.store = SessionStore(storage_dir=Path(self.temp_dir.name))

    def tearDown(self) -> None:
        import backend.api.chat as chat_api
        import backend.api.graph as graph_api
        import backend.api.integration as integration_api
        import backend.api.rag as rag_api
        import backend.api.report as report_api

        from app import app

        app.dependency_overrides.pop(chat_api.get_session_store, None)
        app.dependency_overrides.pop(graph_api.get_session_store, None)
        app.dependency_overrides.pop(integration_api.get_session_store, None)
        app.dependency_overrides.pop(rag_api.get_session_store, None)
        app.dependency_overrides.pop(rag_api.get_llm_client, None)
        app.dependency_overrides.pop(report_api.get_session_store, None)
        self.temp_dir.cleanup()

    def client(self):
        import backend.api.chat as chat_api
        import backend.api.graph as graph_api
        import backend.api.integration as integration_api
        import backend.api.rag as rag_api
        import backend.api.report as report_api

        from app import app
        from fastapi.testclient import TestClient

        app.dependency_overrides[chat_api.get_session_store] = lambda: self.store
        app.dependency_overrides[graph_api.get_session_store] = lambda: self.store
        app.dependency_overrides[integration_api.get_session_store] = lambda: self.store
        app.dependency_overrides[rag_api.get_session_store] = lambda: self.store
        app.dependency_overrides[rag_api.get_llm_client] = lambda: None
        app.dependency_overrides[report_api.get_session_store] = lambda: self.store
        return TestClient(app)

    def test_real_app_mounts_graph_and_rag_routes(self) -> None:
        client = self.client()
        session = self.store.create_session()
        session.selected_textbooks.append("book-1")
        session.chunks.append(
            {
                "chunk_id": "chunk-1",
                "textbook_id": "book-1",
                "textbook_title": "Physiology",
                "chapter": "Energy Metabolism",
                "page_start": 12,
                "page_end": 12,
                "content": "ATP stores energy for cell metabolism. ATP supports transport.",
            }
        )
        self.store.save_session(session)

        graph_build = client.post(
            "/api/graph/build",
            json={"session_id": session.session_id},
        )
        self.assertEqual(graph_build.status_code, 200)
        self.assertGreaterEqual(len(graph_build.json()["nodes"]), 1)

        graph_get = client.get(f"/api/graph?session_id={session.session_id}")
        self.assertEqual(graph_get.status_code, 200)
        self.assertEqual(graph_get.json()["nodes"], graph_build.json()["nodes"])

        rag_status = client.get(f"/api/rag/status?session_id={session.session_id}")
        self.assertEqual(rag_status.status_code, 200)
        self.assertTrue(rag_status.json()["ready"])
        self.assertEqual(rag_status.json()["searchable_chunk_count"], 1)

        rag_query = client.post(
            "/api/rag/query",
            json={"session_id": session.session_id, "question": "ATP energy"},
        )
        self.assertEqual(rag_query.status_code, 200)
        self.assertEqual(rag_query.json()["answer_source"], "fallback")
        self.assertEqual(len(rag_query.json()["retrieved_chunks"]), 1)

        integration_run = client.post(
            "/api/integration/run",
            json={"session_id": session.session_id},
        )
        self.assertEqual(integration_run.status_code, 200)
        self.assertIn("stats", integration_run.json())

        integration_stats = client.get(
            f"/api/integration/stats?session_id={session.session_id}"
        )
        self.assertEqual(integration_stats.status_code, 200)
        self.assertIn("ratio", integration_stats.json()["stats"])

        sankey = client.get(f"/api/integration/sankey?session_id={session.session_id}")
        self.assertEqual(sankey.status_code, 200)
        self.assertIn("nodes", sankey.json())

        report = client.post(
            "/api/report/generate",
            json={"session_id": session.session_id},
        )
        self.assertEqual(report.status_code, 200)
        self.assertIn("KIBot 教材整合报告", report.json()["markdown"])

        chat = client.post(
            "/api/chat/message",
            json={"session_id": session.session_id, "message": "explain ATP"},
        )
        self.assertEqual(chat.status_code, 200)
        self.assertIn("assistant_message", chat.json())


if __name__ == "__main__":
    unittest.main()
