import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class ReportGeneratorTest(unittest.TestCase):
    def make_session(self):
        from backend.schemas.session import KIBotSession

        return KIBotSession(session_id="00000000-0000-0000-0000-000000000001")

    def test_generate_report_includes_required_sections_and_session_metrics(self) -> None:
        from backend.services.report_generator import generate_report_markdown

        session = self.make_session()
        session.selected_textbooks = ["bio-1", "chem-1"]
        session.textbooks = [
            {"id": "bio-1", "title": "Biology", "total_chars": 1200},
            {"id": "chem-1", "title": "Chemistry", "total_chars": 800},
        ]
        session.graph_nodes = [
            {"id": "n1", "name": "ATP", "category": "concept", "textbook_id": "bio-1"},
            {"id": "n2", "name": "Catalyst", "category": "method", "textbook_id": "chem-1"},
        ]
        session.graph_edges = [{"id": "e1", "source": "n1", "target": "n2"}]
        session.integration_decisions = [
            {
                "decision_id": "d1",
                "action": "merge",
                "summary": "Keep ATP explanation and merge overlapping examples.",
                "reason": "Two textbooks cover the same core concept.",
                "compression_ratio": 0.42,
            },
            {
                "decision_id": "d2",
                "action": "keep",
                "summary": "Retain catalyst lab safety details.",
            },
        ]
        session.token_usage.calls = 3
        session.token_usage.input_tokens = 150
        session.token_usage.output_tokens = 50
        session.token_usage.total_tokens = 200

        markdown = generate_report_markdown(session)

        for heading in (
            "## 整合概览",
            "## 整合决策摘要",
            "## 知识图谱统计",
            "## 重点整合案例",
            "## 教学完整性说明",
            "## 局限与改进",
        ):
            self.assertIn(heading, markdown)
        self.assertIn("已选择教材：2 本", markdown)
        self.assertIn("知识图谱节点：2 个", markdown)
        self.assertIn("知识图谱边：1 条", markdown)
        self.assertIn("Token 使用：200", markdown)
        self.assertIn("压缩比例：42.00%", markdown)
        self.assertIn("d1", markdown)
        self.assertIn("Keep ATP explanation", markdown)

    def test_generate_report_handles_empty_session_gracefully(self) -> None:
        from backend.services.report_generator import generate_report_markdown

        markdown = generate_report_markdown(self.make_session())

        self.assertIn("## 整合概览", markdown)
        self.assertIn("已选择教材：0 本", markdown)
        self.assertIn("暂无整合决策", markdown)
        self.assertIn("暂无知识图谱节点", markdown)
        self.assertIn("报告基于当前会话数据生成", markdown)


if __name__ == "__main__":
    unittest.main()
