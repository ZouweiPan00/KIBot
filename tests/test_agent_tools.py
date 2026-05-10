import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class AgentToolsTest(unittest.TestCase):
    def make_session(self):
        from backend.schemas.session import KIBotSession

        return KIBotSession(session_id="tool-test")

    def test_get_selected_textbooks_resolves_ids_and_keeps_dict_payloads(self) -> None:
        from backend.tools.textbook_tool import get_selected_textbooks

        session = self.make_session()
        session.selected_textbooks = ["book-1", {"id": "manual", "title": "Manual"}]
        session.textbooks = [
            {"id": "book-1", "title": "Biology", "total_chars": 1200},
            SimpleNamespace(id="book-2", title="Chemistry", total_chars=800),
        ]

        selected = get_selected_textbooks(session)

        self.assertEqual(
            selected,
            [
                {"id": "book-1", "title": "Biology", "total_chars": 1200},
                {"id": "manual", "title": "Manual"},
            ],
        )

    def test_compression_stats_and_token_usage_handle_dict_and_object_items(self) -> None:
        from backend.tools.stats_tool import get_compression_stats, get_token_usage

        session = self.make_session()
        session.textbooks = [
            {"id": "book-1", "total_chars": 1000},
            SimpleNamespace(id="book-2", total_chars=500),
            {"id": "missing-count"},
        ]
        session.integration_decisions = [
            {"decision_id": "d1", "compact": "short core"},
            SimpleNamespace(decision_id="d2", summary="another compact note"),
            {"decision_id": "d3", "reason": "no compact text"},
        ]
        session.token_usage.calls = 2
        session.token_usage.input_tokens = 30
        session.token_usage.output_tokens = 12
        session.token_usage.total_tokens = 42

        stats = get_compression_stats(session)
        usage = get_token_usage(session)

        self.assertEqual(stats["original_chars"], 1500)
        self.assertEqual(stats["compressed_chars"], len("short core") + len("another compact note"))
        self.assertAlmostEqual(
            stats["compression_ratio"],
            stats["compressed_chars"] / 1500,
        )
        self.assertEqual(
            usage,
            {
                "calls": 2,
                "input_tokens": 30,
                "output_tokens": 12,
                "total_tokens": 42,
            },
        )

    def test_graph_summary_counts_nodes_edges_and_categories(self) -> None:
        from backend.tools.stats_tool import get_graph_summary

        session = self.make_session()
        session.graph_nodes = [
            {"id": "n1", "category": "concept", "textbook_id": "book-1"},
            SimpleNamespace(id="n2", category="method", textbook_id="book-1"),
            {"id": "n3", "category": "concept", "textbook_id": "book-2"},
        ]
        session.graph_edges = [
            {"id": "e1", "source": "n1", "target": "n2"},
            SimpleNamespace(id="e2", source="n2", target="n3"),
        ]

        summary = get_graph_summary(session)

        self.assertEqual(summary["node_count"], 3)
        self.assertEqual(summary["edge_count"], 2)
        self.assertEqual(summary["categories"], {"concept": 2, "method": 1})
        self.assertEqual(summary["textbooks"], {"book-1": 2, "book-2": 1})

    def test_decision_tools_read_and_mutate_matching_decision_in_memory(self) -> None:
        from backend.tools.decision_tool import get_integration_decisions, update_decision

        session = self.make_session()
        object_decision = SimpleNamespace(
            decision_id="d2",
            action="remove",
            teacher_note="",
            status="pending",
        )
        session.integration_decisions = [
            {"decision_id": "d1", "action": "merge", "teacher_note": ""},
            object_decision,
        ]

        updated = update_decision(session, "d2", "keep", "Keep it for assessment.")

        self.assertIs(updated, object_decision)
        self.assertEqual(object_decision.action, "keep")
        self.assertEqual(object_decision.teacher_note, "Keep it for assessment.")
        self.assertEqual(object_decision.status, "teacher_updated")
        self.assertEqual(get_integration_decisions(session)[0]["decision_id"], "d1")

    def test_update_decision_raises_for_unknown_decision_id(self) -> None:
        from backend.tools.decision_tool import update_decision

        session = self.make_session()
        session.integration_decisions = [{"decision_id": "d1", "action": "merge"}]

        with self.assertRaisesRegex(ValueError, "Decision not found"):
            update_decision(session, "missing", "keep", "")

    def test_report_tool_returns_report_state(self) -> None:
        from backend.tools.report_tool import get_report

        session = self.make_session()
        session.report.markdown = "# Core Report"
        session.report.updated_at = "2026-05-10T12:00:00Z"

        self.assertEqual(
            get_report(session),
            {
                "markdown": "# Core Report",
                "updated_at": "2026-05-10T12:00:00Z",
            },
        )


if __name__ == "__main__":
    unittest.main()
