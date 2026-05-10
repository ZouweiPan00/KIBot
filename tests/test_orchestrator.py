import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeLLMClient:
    def __init__(self) -> None:
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return type(
            "LLMResponse",
            (),
            {"answer_text": "The selected concepts should be merged carefully."},
        )()


class OrchestratorTest(unittest.TestCase):
    def make_session(self):
        from backend.schemas.session import KIBotSession

        session = KIBotSession(session_id="orchestrator-test")
        session.selected_textbooks = ["book-1"]
        session.textbooks = [{"id": "book-1", "title": "Biology", "total_chars": 1000}]
        session.graph_nodes = [{"id": "n1", "category": "concept", "textbook_id": "book-1"}]
        session.graph_edges = []
        session.integration_decisions = [
            {
                "decision_id": "d1",
                "action": "merge",
                "concept": "Cell division",
                "summary": "compact",
            }
        ]
        session.memory_summary = "Teacher prefers concise chapter-level reports."
        return session

    def test_build_context_uses_session_grounded_tools(self) -> None:
        from backend.agent.orchestrator import KIBotOrchestrator

        context = KIBotOrchestrator().build_context(self.make_session())

        self.assertEqual(context["session_id"], "orchestrator-test")
        self.assertEqual(context["selected_textbooks"][0]["title"], "Biology")
        self.assertEqual(context["compression_stats"]["original_chars"], 1000)
        self.assertEqual(context["graph_summary"]["node_count"], 1)
        self.assertEqual(context["integration_decisions"][0]["decision_id"], "d1")
        self.assertEqual(
            context["memory_summary"],
            "Teacher prefers concise chapter-level reports.",
        )

    def test_answer_returns_deterministic_summary_without_llm_for_status_question(self) -> None:
        from backend.agent.orchestrator import KIBotOrchestrator

        llm = FakeLLMClient()
        result = KIBotOrchestrator(llm_client=llm).answer(
            self.make_session(),
            "show current stats",
        )

        self.assertFalse(result["used_llm"])
        self.assertEqual(llm.calls, [])
        self.assertIn("1 selected textbook", result["answer"])
        self.assertIn("1 integration decision", result["answer"])

    def test_answer_calls_injected_llm_for_explanatory_question(self) -> None:
        from backend.agent.orchestrator import KIBotOrchestrator

        llm = FakeLLMClient()
        result = KIBotOrchestrator(llm_client=llm).answer(
            self.make_session(),
            "Why merge the cell division concepts?",
        )

        self.assertTrue(result["used_llm"])
        self.assertEqual(result["answer"], "The selected concepts should be merged carefully.")
        self.assertEqual(len(llm.calls), 1)
        serialized_messages = "\n".join(message["content"] for message in llm.calls[0])
        self.assertIn("Cell division", serialized_messages)
        self.assertIn("Teacher prefers concise", serialized_messages)

    def test_answer_falls_back_to_deterministic_summary_when_llm_is_not_available(self) -> None:
        from backend.agent.orchestrator import KIBotOrchestrator

        result = KIBotOrchestrator().answer(
            self.make_session(),
            "Why merge the cell division concepts?",
        )

        self.assertFalse(result["used_llm"])
        self.assertIn("No LLM client is configured", result["answer"])


if __name__ == "__main__":
    unittest.main()
