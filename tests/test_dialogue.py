import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class DialogueServiceTest(unittest.TestCase):
    def session_with_decisions(self):
        from backend.schemas.session import KIBotSession

        session = KIBotSession(session_id="11111111-1111-1111-1111-111111111111")
        session.graph_nodes = [
            {
                "id": "bio:atp",
                "name": "ATP",
                "textbook_id": "bio",
                "status": "active",
            },
            {
                "id": "bio:mitochondria",
                "name": "Mitochondria",
                "textbook_id": "bio",
                "status": "active",
            },
        ]
        session.integration_decisions = [
            {
                "decision_id": "dec-atp",
                "action": "merge",
                "concept_name": "ATP",
                "sources": [{"node_id": "bio:atp", "name": "ATP"}],
                "reason": "same abbreviation across books",
                "confidence": 0.9,
                "compact_note": "Merge ATP into one teaching point.",
                "teacher_note": "",
            },
            {
                "decision_id": "dec-mito",
                "action": "keep",
                "concept_name": "Mitochondria",
                "sources": [{"node_id": "bio:mitochondria", "name": "Mitochondria"}],
                "reason": "unique concept",
                "confidence": 0.7,
                "compact_note": "Keep mitochondria.",
                "teacher_note": "",
            },
        ]
        return session

    def test_parse_intents_with_rule_fallback(self) -> None:
        from backend.services.dialogue import DialogueService

        service = DialogueService()

        self.assertEqual(
            service.parse_intent("Explain the decision for ATP").type,
            "explain_decision",
        )
        self.assertEqual(
            service.parse_intent("Keep ATP in the lesson").type,
            "keep_concept",
        )
        self.assertEqual(
            service.parse_intent("Remove mitochondria").type,
            "remove_concept",
        )
        merge = service.parse_intent("Merge ATP and energy currency")
        self.assertEqual(merge.type, "merge_concepts")
        self.assertEqual(merge.concepts, ["ATP", "energy currency"])
        self.assertEqual(
            service.parse_intent("Split mitochondria into two concepts").type,
            "split_concept",
        )

    def test_keep_and_remove_update_decision_graph_and_messages(self) -> None:
        from backend.services.dialogue import DialogueService

        session = self.session_with_decisions()
        service = DialogueService()

        keep_result = service.handle_message(session, "Please keep ATP")
        remove_result = service.handle_message(session, "Remove mitochondria")

        self.assertEqual(keep_result.parsed_intent["type"], "keep_concept")
        self.assertEqual(session.integration_decisions[0]["action"], "keep")
        self.assertEqual(session.graph_nodes[0]["status"], "active")
        self.assertIn("Teacher requested keep", session.integration_decisions[0]["teacher_note"])

        self.assertEqual(remove_result.parsed_intent["type"], "remove_concept")
        self.assertEqual(session.integration_decisions[1]["action"], "remove")
        self.assertEqual(session.graph_nodes[1]["status"], "removed")
        self.assertIn("Teacher requested remove", session.integration_decisions[1]["teacher_note"])

        self.assertEqual([message["role"] for message in session.messages], [
            "user",
            "assistant",
            "user",
            "assistant",
        ])
        self.assertEqual(remove_result.state_summary["message_count"], 4)
        self.assertEqual(remove_result.state_summary["decision_count"], 2)

    def test_explain_and_missing_targets_are_safe(self) -> None:
        from backend.services.dialogue import DialogueService

        session = self.session_with_decisions()
        service = DialogueService()

        explain = service.handle_message(session, "Explain decision dec-atp")
        missing = service.handle_message(session, "Remove glycolysis")

        self.assertIn("same abbreviation", explain.assistant_message)
        self.assertEqual(session.integration_decisions[0]["action"], "merge")
        self.assertIn("could not find", missing.assistant_message.lower())
        self.assertEqual(session.integration_decisions[0]["action"], "merge")
        self.assertEqual(session.integration_decisions[1]["action"], "keep")

    def test_merge_and_split_update_decision_graph_and_report_state(self) -> None:
        from backend.services.dialogue import DialogueService

        session = self.session_with_decisions()
        service = DialogueService()

        split_result = service.handle_message(session, "Split ATP")
        merge_result = service.handle_message(session, "Merge ATP and energy currency")

        self.assertEqual(split_result.parsed_intent["type"], "split_concept")
        self.assertEqual(session.integration_decisions[0]["action"], "merge")
        self.assertEqual(session.graph_nodes[0]["status"], "merged")
        self.assertIn("Teacher requested merge", session.integration_decisions[0]["teacher_note"])
        self.assertIn("teacher dialogue", session.report.markdown.lower())
        self.assertIsNotNone(session.report.updated_at)
        self.assertEqual(merge_result.state_summary["decisions"]["dec-atp"], "merge")

    def test_compacts_older_messages_after_ten_turns(self) -> None:
        from backend.services.dialogue import DialogueService

        session = self.session_with_decisions()
        for index in range(11):
            session.messages.extend(
                [
                    {"role": "user", "content": f"old user {index}"},
                    {"role": "assistant", "content": f"old assistant {index}"},
                ]
            )

        result = DialogueService().handle_message(session, "Explain ATP")

        self.assertLessEqual(len(session.messages), 10)
        self.assertIn("old user 0", session.memory_summary)
        self.assertIn("old assistant 6", session.memory_summary)
        self.assertEqual(session.messages[-2]["content"], "Explain ATP")
        self.assertEqual(session.messages[-1]["role"], "assistant")
        self.assertTrue(result.state_summary["memory_summary"])


if __name__ == "__main__":
    unittest.main()
