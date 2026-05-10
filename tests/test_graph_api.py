import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class GraphApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

        from backend.services.session_store import SessionStore

        self.store = SessionStore(storage_dir=Path(self.temp_dir.name))
        self.app = None
        self.graph_dependency = None

    def tearDown(self) -> None:
        if self.app is not None and self.graph_dependency is not None:
            self.app.dependency_overrides.pop(self.graph_dependency, None)
        self.temp_dir.cleanup()

    def client(self):
        import backend.api.graph as graph_api

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(graph_api.router)
        app.dependency_overrides[graph_api.get_session_store] = lambda: self.store
        self.app = app
        self.graph_dependency = graph_api.get_session_store
        return TestClient(app)

    def test_build_graph_persists_nodes_and_edges_on_session(self) -> None:
        client = self.client()
        session = self.store.create_session()
        session.selected_textbooks.append("bio-1")
        session.integration_decisions.append({"decision_id": "stale"})
        session.report.markdown = "stale report"
        session.chunks.extend(
            [
                {
                    "chunk_id": "chunk-1",
                    "textbook_id": "bio-1",
                    "textbook_title": "Biology 101",
                    "chapter": "Cell Structure",
                    "page_start": 7,
                    "content": (
                        "Mitochondria produce ATP. "
                        "Cell membranes regulate transport."
                    ),
                },
                {
                    "chunk_id": "chunk-2",
                    "textbook_id": "math-1",
                    "textbook_title": "Math",
                    "chapter": "Algebra",
                    "page_start": 2,
                    "content": "Quadratic equations use polynomials.",
                },
            ]
        )
        self.store.save_session(session)

        response = client.post(
            "/api/graph/build",
            json={"session_id": session.session_id},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        node_ids = [node["id"] for node in payload["nodes"]]
        self.assertIn("bio-1:mitochondria", node_ids)
        self.assertNotIn("math-1:quadratic", node_ids)
        self.assertGreaterEqual(len(payload["edges"]), 1)

        saved = self.store.get_session(session.session_id)
        self.assertEqual(saved.graph_nodes, payload["nodes"])
        self.assertEqual(saved.graph_edges, payload["edges"])
        self.assertEqual(saved.integration_decisions, [])
        self.assertEqual(saved.report.markdown, "")

    def test_get_graph_returns_saved_session_graph(self) -> None:
        client = self.client()
        session = self.store.create_session()
        session.graph_nodes.append(
            {
                "id": "bio-1:atp",
                "name": "Atp",
                "definition": "Concept from Cell Structure.",
                "category": "concept",
                "textbook_id": "bio-1",
                "textbook_title": "Biology 101",
                "chapter": "Cell Structure",
                "page": 7,
                "frequency": 1,
                "importance": 1.0,
                "status": "active",
            }
        )
        session.graph_edges.append(
            {
                "id": "bio-1:atp->bio-1:mitochondria:co_occurs",
                "source": "bio-1:atp",
                "target": "bio-1:mitochondria",
                "relation_type": "co_occurs",
                "description": "Atp appears with Mitochondria.",
                "confidence": 0.55,
            }
        )
        self.store.save_session(session)

        response = client.get(f"/api/graph?session_id={session.session_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["nodes"], session.graph_nodes)
        self.assertEqual(response.json()["edges"], session.graph_edges)

    def test_build_graph_can_use_ai_client_and_record_token_usage(self) -> None:
        import backend.api.graph as graph_api

        class FakeUsage:
            calls = 1
            input_tokens = 9
            output_tokens = 7
            total_tokens = 16

        class FakeResponse:
            answer_text = """
            {
              "nodes": [
                {
                  "name": "上皮组织",
                  "definition": "覆盖体表和腔面的组织。",
                  "textbook_id": "book-1",
                  "textbook_title": "01__",
                  "chapter": "绪论",
                  "page": 1,
                  "frequency": 2,
                  "importance": 3
                }
              ],
              "edges": []
            }
            """
            token_usage = FakeUsage()

        class FakeGraphClient:
            def __init__(self) -> None:
                self.token_usage = None
                self.closed = False

            def chat(self, _messages):
                self.token_usage = FakeUsage()
                return FakeResponse()

            def close(self) -> None:
                self.closed = True

        fake_client = FakeGraphClient()
        original_factory = graph_api._graph_llm_client
        graph_api._graph_llm_client = lambda use_ai: fake_client if use_ai else None
        self.addCleanup(lambda: setattr(graph_api, "_graph_llm_client", original_factory))

        client = self.client()
        session = self.store.create_session()
        session.selected_textbooks.append("book-1")
        session.chunks.append(
            {
                "chunk_id": "chunk-1",
                "textbook_id": "book-1",
                "textbook_title": "01__",
                "chapter": "绪论",
                "page_start": 1,
                "content": "上皮组织覆盖体表。",
            }
        )
        self.store.save_session(session)

        response = client.post(
            "/api/graph/build",
            json={"session_id": session.session_id, "use_ai": True},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["nodes"][0]["name"], "上皮组织")
        self.assertTrue(fake_client.closed)

        saved = self.store.get_session(session.session_id)
        self.assertEqual(saved.token_usage.calls, 1)
        self.assertEqual(saved.token_usage.total_tokens, 16)

    def test_graph_endpoints_validate_session_id(self) -> None:
        client = self.client()

        invalid_build = client.post("/api/graph/build", json={"session_id": "bad"})
        self.assertEqual(invalid_build.status_code, 400)

        unknown_get = client.get(f"/api/graph?session_id={uuid4()}")
        self.assertEqual(unknown_get.status_code, 404)


if __name__ == "__main__":
    unittest.main()
