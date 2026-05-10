import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class ChatApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

        from backend.services.session_store import SessionStore

        self.store = SessionStore(storage_dir=Path(self.temp_dir.name))
        self.app = None
        self.chat_dependency = None

    def tearDown(self) -> None:
        if self.app is not None and self.chat_dependency is not None:
            self.app.dependency_overrides.pop(self.chat_dependency, None)
        self.temp_dir.cleanup()

    def client(self, llm_client=None):
        import backend.api.chat as chat_api

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(chat_api.router)
        app.dependency_overrides[chat_api.get_session_store] = lambda: self.store
        app.dependency_overrides[chat_api.get_llm_client] = lambda: llm_client
        self.app = app
        self.chat_dependency = chat_api.get_session_store
        return TestClient(app)

    def session_with_decision(self):
        session = self.store.create_session()
        session.graph_nodes.append(
            {
                "id": "bio:atp",
                "name": "ATP",
                "textbook_id": "bio",
                "status": "active",
            }
        )
        session.integration_decisions.append(
            {
                "decision_id": "dec-atp",
                "action": "merge",
                "concept_name": "ATP",
                "sources": [{"node_id": "bio:atp", "name": "ATP"}],
                "reason": "same abbreviation across books",
                "confidence": 0.9,
                "compact_note": "Merge ATP into one teaching point.",
                "teacher_note": "",
            }
        )
        return self.store.save_session(session)

    def test_post_message_updates_and_persists_session_state(self) -> None:
        client = self.client()
        session = self.session_with_decision()

        response = client.post(
            "/api/chat/message",
            json={"session_id": session.session_id, "message": "Keep ATP"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("assistant_message", payload)
        self.assertEqual(payload["parsed_intent"]["type"], "keep_concept")
        self.assertEqual(payload["state_summary"]["message_count"], 2)
        self.assertEqual(payload["state_summary"]["decisions"]["dec-atp"], "keep")

        saved = self.store.get_session(session.session_id)
        self.assertEqual(saved.integration_decisions[0]["action"], "keep")
        self.assertEqual([message["role"] for message in saved.messages], ["user", "assistant"])

    def test_post_message_uses_llm_client_when_available_and_records_tokens(self) -> None:
        calls = []

        class FakeLLM:
            def chat(self, messages):
                calls.append(messages)
                return SimpleNamespace(
                    answer_text="AI: ATP should stay merged because the evidence overlaps.",
                    token_usage=SimpleNamespace(
                        calls=1,
                        input_tokens=12,
                        output_tokens=9,
                        total_tokens=21,
                    ),
                )

        client = self.client(llm_client=FakeLLM())
        session = self.session_with_decision()

        response = client.post(
            "/api/chat/message",
            json={"session_id": session.session_id, "message": "请解释 ATP 为什么要合并"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["assistant_message"],
            "AI: ATP should stay merged because the evidence overlaps.",
        )
        self.assertEqual(payload["parsed_intent"]["source"], "rule")
        self.assertIn("请解释 ATP 为什么要合并", calls[0][1]["content"])

        saved = self.store.get_session(session.session_id)
        self.assertEqual(saved.token_usage.calls, 1)
        self.assertEqual(saved.token_usage.total_tokens, 21)

    def test_post_message_validates_session_and_body(self) -> None:
        client = self.client()

        invalid = client.post(
            "/api/chat/message",
            json={"session_id": "bad", "message": "Keep ATP"},
        )
        unknown = client.post(
            "/api/chat/message",
            json={"session_id": str(uuid4()), "message": "Keep ATP"},
        )
        blank = client.post(
            "/api/chat/message",
            json={"session_id": str(uuid4()), "message": "   "},
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(blank.status_code, 422)


if __name__ == "__main__":
    unittest.main()
