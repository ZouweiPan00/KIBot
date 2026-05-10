import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class RagApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

        from backend.services.session_store import SessionStore

        self.store = SessionStore(storage_dir=Path(self.temp_dir.name))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def client(self, llm_client=None):
        import backend.api.rag as rag_api

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(rag_api.router)
        app.dependency_overrides[rag_api.get_session_store] = lambda: self.store
        app.dependency_overrides[rag_api.get_llm_client] = lambda: llm_client
        return TestClient(app)

    def session_with_chunks(self):
        session = self.store.create_session()
        session.selected_textbooks.append("book-1")
        session.graph_nodes.append({"node_id": "concept-atp", "name": "ATP"})
        session.chunks.extend(
            [
                {
                    "chunk_id": "chunk-atp",
                    "textbook_id": "book-1",
                    "textbook_title": "Biology",
                    "chapter": "Cell Energy",
                    "page_start": 3,
                    "page_end": 4,
                    "content": "ATP transfers energy inside cells.",
                },
                {
                    "chunk_id": "chunk-dna",
                    "textbook_id": "book-1",
                    "textbook_title": "Biology",
                    "chapter": "Genetics",
                    "page_start": 20,
                    "page_end": 20,
                    "content": "DNA carries genetic information.",
                },
            ]
        )
        return self.store.save_session(session)

    def test_status_reports_session_readiness(self) -> None:
        client = self.client()
        session = self.session_with_chunks()

        response = client.get(f"/api/rag/status?session_id={session.session_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "session_id": session.session_id,
                "ready": True,
                "chunk_count": 2,
                "selected_textbook_count": 1,
                "searchable_chunk_count": 2,
                "graph_node_count": 1,
                "retrieval_status": "ready",
            },
        )

    def test_query_returns_llm_answer_citations_and_retrieved_scores_with_opt_in(self) -> None:
        calls = []

        class FakeLLM:
            def chat(self, messages):
                calls.append(messages)
                return SimpleNamespace(answer_text="ATP transfers energy. [1]")

        client = self.client(llm_client=FakeLLM())
        session = self.session_with_chunks()

        response = client.post(
            "/api/rag/query",
            json={"session_id": session.session_id, "question": "What does ATP do?", "use_llm": True},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"], "ATP transfers energy. [1]")
        self.assertEqual(payload["citations"][0]["chunk_id"], "chunk-atp")
        self.assertEqual(payload["retrieved_chunks"][0]["chunk"]["chunk_id"], "chunk-atp")
        self.assertGreater(payload["retrieved_chunks"][0]["score"], 0)
        self.assertIn("What does ATP do?", calls[0][1]["content"])

    def test_query_does_not_call_llm_without_explicit_opt_in(self) -> None:
        calls = []

        class FakeLLM:
            def chat(self, messages):
                calls.append(messages)
                return SimpleNamespace(answer_text="This should not be used. [1]")

        client = self.client(llm_client=FakeLLM())
        session = self.session_with_chunks()

        response = client.post(
            "/api/rag/query",
            json={"session_id": session.session_id, "question": "What does ATP do?"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [])
        self.assertIn("ATP transfers energy", response.json()["answer"])
        self.assertEqual(response.json()["answer_source"], "fallback")

    def test_query_reports_llm_error_when_opted_in_client_fails(self) -> None:
        class BrokenLLM:
            def chat(self, messages):
                raise RuntimeError("provider unavailable")

        client = self.client(llm_client=BrokenLLM())
        session = self.session_with_chunks()

        response = client.post(
            "/api/rag/query",
            json={"session_id": session.session_id, "question": "What does ATP do?", "use_llm": True},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("ATP transfers energy", payload["answer"])
        self.assertEqual(payload["answer_source"], "fallback")
        self.assertIn("llm_error", payload)
        self.assertNotIn("sk-", payload["llm_error"])

    def test_query_accepts_query_alias_and_falls_back_without_llm(self) -> None:
        client = self.client(llm_client=None)
        session = self.session_with_chunks()

        response = client.post(
            "/api/rag/query",
            json={"session_id": session.session_id, "query": "ATP"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("ATP transfers energy", response.json()["answer"])

    def test_status_and_query_validate_session_id(self) -> None:
        client = self.client()

        invalid = client.get("/api/rag/status?session_id=not-a-uuid")
        unknown = client.post(
            "/api/rag/query",
            json={"session_id": str(uuid4()), "question": "Anything?"},
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(unknown.status_code, 404)

    def test_query_requires_question_or_query_text(self) -> None:
        client = self.client()
        session = self.store.create_session()

        response = client.post(
            "/api/rag/query",
            json={"session_id": session.session_id, "question": "   "},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
