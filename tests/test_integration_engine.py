import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class IntegrationEngineTest(unittest.TestCase):
    def test_run_integration_merges_similar_selected_graph_nodes_and_budgets_notes(self) -> None:
        from backend.schemas.session import KIBotSession
        from backend.services.integration_engine import run_integration

        session = KIBotSession(session_id="11111111-1111-1111-1111-111111111111")
        session.selected_textbooks = ["pathology", "immunology"]
        session.textbooks = [
            {"textbook_id": "pathology", "title": "病理学", "total_chars": 1200},
            {"textbook_id": "immunology", "title": "免疫学", "total_chars": 800},
            {"textbook_id": "surgery", "title": "外科学", "total_chars": 5000},
        ]
        session.graph_nodes = [
            {
                "id": "pathology:inflammation",
                "name": "炎症",
                "textbook_id": "pathology",
                "textbook_title": "病理学",
                "chapter": "急性炎症",
                "definition": "炎症 involves vascular response and immune cells.",
            },
            {
                "id": "immunology:inflammatory-response",
                "name": "炎症反应",
                "textbook_id": "immunology",
                "textbook_title": "免疫学",
                "chapter": "固有免疫",
                "definition": "炎症反应 recruits immune cells during tissue injury.",
            },
            {
                "id": "surgery:inflammation",
                "name": "炎症",
                "textbook_id": "surgery",
                "textbook_title": "外科学",
                "chapter": "感染",
                "definition": "Unselected textbook node must be ignored.",
            },
        ]

        result = run_integration(session)

        merge_decisions = [
            decision for decision in result.decisions if decision["action"] == "merge"
        ]
        self.assertEqual(len(merge_decisions), 1)
        decision = merge_decisions[0]
        self.assertEqual(decision["concept_name"], "炎症")
        self.assertEqual(
            {source["textbook_id"] for source in decision["sources"]},
            {"pathology", "immunology"},
        )
        self.assertIn("containment", decision["reason"])
        self.assertGreaterEqual(decision["confidence"], 0.7)
        self.assertLessEqual(result.stats["ratio"], 0.30)
        self.assertEqual(result.stats["original_chars"], 2000)
        self.assertEqual(
            result.stats["compressed_chars"],
            sum(len(decision["compact_note"]) for decision in result.decisions),
        )

        sankey = result.sankey
        self.assertIn({"name": "病理学-炎症"}, sankey["nodes"])
        self.assertIn({"name": "免疫学-炎症反应"}, sankey["nodes"])
        self.assertIn({"name": "整合-炎症"}, sankey["nodes"])
        self.assertIn(
            {"source": "病理学-炎症", "target": "整合-炎症", "value": 1},
            sankey["links"],
        )

    def test_run_integration_falls_back_to_selected_chunks(self) -> None:
        from backend.schemas.session import KIBotSession
        from backend.services.integration_engine import run_integration

        session = KIBotSession(session_id="22222222-2222-2222-2222-222222222222")
        session.selected_textbooks = ["bio-a", "bio-b"]
        session.textbooks = [
            {"id": "bio-a", "title": "Book A", "total_chars": 1000},
            {"id": "bio-b", "title": "Book B", "total_chars": 1000},
        ]
        session.chunks = [
            {
                "chunk_id": "a-1",
                "textbook_id": "bio-a",
                "textbook_title": "Book A",
                "chapter": "Cell Energy",
                "content": "ATP powers transport. ATP supports metabolism.",
            },
            {
                "chunk_id": "b-1",
                "textbook_id": "bio-b",
                "textbook_title": "Book B",
                "chapter": "Energy Molecules",
                "content": "ATP stores energy for metabolism.",
            },
            {
                "chunk_id": "c-1",
                "textbook_id": "bio-c",
                "textbook_title": "Book C",
                "chapter": "Ignored",
                "content": "ATP should not appear from unselected books.",
            },
        ]

        result = run_integration(session)

        merge = next(decision for decision in result.decisions if decision["action"] == "merge")
        self.assertEqual(merge["concept_name"], "Atp")
        self.assertEqual(
            {source["textbook_id"] for source in merge["sources"]},
            {"bio-a", "bio-b"},
        )

    def test_update_decision_mutates_only_action_and_teacher_note(self) -> None:
        from backend.services.integration_engine import update_decision

        decisions = [
            {
                "decision_id": "d1",
                "action": "merge",
                "teacher_note": "",
                "reason": "same name",
            },
            {
                "decision_id": "d2",
                "action": "keep",
                "teacher_note": "unchanged",
                "reason": "unique",
            },
        ]

        updated = update_decision(
            decisions,
            "d1",
            action="split",
            teacher_note="Teach separately.",
        )

        self.assertTrue(updated)
        self.assertEqual(decisions[0]["action"], "split")
        self.assertEqual(decisions[0]["teacher_note"], "Teach separately.")
        self.assertEqual(decisions[0]["reason"], "same name")
        self.assertEqual(decisions[1]["action"], "keep")


if __name__ == "__main__":
    unittest.main()
