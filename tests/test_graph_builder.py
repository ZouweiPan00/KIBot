import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class GraphBuilderTest(unittest.TestCase):
    def test_builds_deterministic_nodes_and_edges_from_selected_chunks(self) -> None:
        from backend.services.graph_builder import build_knowledge_graph

        chunks = [
            {
                "chunk_id": "chunk-1",
                "textbook_id": "bio-1",
                "textbook_title": "Biology 101",
                "chapter": "Cell Structure",
                "page_start": 7,
                "content": (
                    "Mitochondria produce ATP in cells. "
                    "Mitochondria support cellular respiration."
                ),
            },
            {
                "chunk_id": "chunk-2",
                "textbook_id": "bio-1",
                "textbook_title": "Biology 101",
                "chapter": "Cell Structure",
                "page_start": 8,
                "content": "ATP stores energy for cellular respiration.",
            },
        ]

        graph = build_knowledge_graph(chunks, selected_textbook_ids=["bio-1"])

        node_ids = [node.id for node in graph.nodes]
        self.assertIn("bio-1:mitochondria", node_ids)
        self.assertIn("bio-1:atp", node_ids)
        self.assertEqual(node_ids, sorted(node_ids))

        mitochondria = next(node for node in graph.nodes if node.id == "bio-1:mitochondria")
        self.assertEqual(mitochondria.name, "Mitochondria")
        self.assertEqual(mitochondria.category, "concept")
        self.assertEqual(mitochondria.textbook_id, "bio-1")
        self.assertEqual(mitochondria.textbook_title, "Biology 101")
        self.assertEqual(mitochondria.chapter, "Cell Structure")
        self.assertEqual(mitochondria.page, 7)
        self.assertEqual(mitochondria.frequency, 2)
        self.assertGreaterEqual(mitochondria.importance, 1.0)
        self.assertEqual(mitochondria.status, "active")
        self.assertIn("Cell Structure", mitochondria.definition)

        edge_ids = [edge.id for edge in graph.edges]
        self.assertIn("bio-1:atp->bio-1:mitochondria:co_occurs", edge_ids)
        edge = next(
            edge
            for edge in graph.edges
            if edge.id == "bio-1:atp->bio-1:mitochondria:co_occurs"
        )
        self.assertEqual(edge.source, "bio-1:atp")
        self.assertEqual(edge.target, "bio-1:mitochondria")
        self.assertEqual(edge.relation_type, "co_occurs")
        self.assertGreater(edge.confidence, 0)

    def test_limits_nodes_per_textbook_and_total_visible_nodes(self) -> None:
        from backend.services.graph_builder import build_knowledge_graph

        chunks = []
        for textbook_number in range(6):
            textbook_id = f"book-{textbook_number}"
            words = [f"Concept{textbook_number}_{index}" for index in range(35)]
            chunks.append(
                {
                    "chunk_id": f"chunk-{textbook_number}",
                    "textbook_id": textbook_id,
                    "textbook_title": f"Book {textbook_number}",
                    "chapter": "Overview",
                    "page_start": 1,
                    "content": " ".join(words),
                }
            )

        graph = build_knowledge_graph(
            chunks,
            selected_textbook_ids=[f"book-{index}" for index in range(6)],
        )

        self.assertLessEqual(len(graph.nodes), 150)
        for textbook_number in range(6):
            textbook_id = f"book-{textbook_number}"
            count = sum(1 for node in graph.nodes if node.textbook_id == textbook_id)
            self.assertLessEqual(count, 30)

    def test_uses_all_chunks_when_no_selection_is_provided(self) -> None:
        from backend.services.graph_builder import build_knowledge_graph

        graph = build_knowledge_graph(
            [
                {
                    "chunk_id": "chunk-1",
                    "textbook_id": "math-1",
                    "textbook_title": "Math",
                    "chapter": "Algebra",
                    "page_start": 3,
                    "content": "Quadratic equations include polynomials.",
                }
            ]
        )

        self.assertTrue(graph.nodes)
        self.assertEqual({node.textbook_id for node in graph.nodes}, {"math-1"})

    def test_extracts_fallback_concepts_from_chunk_content_without_title_noise(self) -> None:
        from backend.services.graph_builder import build_knowledge_graph

        graph = build_knowledge_graph(
            [
                {
                    "chunk_id": "chunk-1",
                    "textbook_id": "bio-1",
                    "textbook_title": "Cell Biology",
                    "chapter": "Membrane Transport",
                    "page_start": 4,
                    "content": "Membrane transport depends on diffusion gradients.",
                }
            ]
        )

        self.assertIn("bio-1:membrane", [node.id for node in graph.nodes])
        self.assertNotIn("bio-1:cell", [node.id for node in graph.nodes])

    def test_extracts_chinese_concepts_from_selected_chunks(self) -> None:
        from backend.services.graph_builder import build_knowledge_graph

        graph = build_knowledge_graph(
            [
                {
                    "chunk_id": "chunk-1",
                    "textbook_id": "bio-1",
                    "textbook_title": "生物学",
                    "chapter": "细胞结构",
                    "page_start": 9,
                    "content": "细胞膜 调节 物质运输。细胞膜 保护细胞。",
                }
            ],
            selected_textbook_ids=["bio-1"],
        )

        node_ids = [node.id for node in graph.nodes]
        self.assertIn("bio-1:细胞膜", node_ids)
        membrane = next(node for node in graph.nodes if node.id == "bio-1:细胞膜")
        self.assertEqual(membrane.name, "细胞膜")
        self.assertEqual(membrane.frequency, 2)

    def test_filters_chapter_heading_tokens_from_chinese_concepts(self) -> None:
        from backend.services.graph_builder import build_knowledge_graph

        graph = build_knowledge_graph(
            [
                {
                    "chunk_id": "chunk-1",
                    "textbook_id": "bio-1",
                    "textbook_title": "组织学与胚胎学",
                    "chapter": "第二章 上皮组织",
                    "page_start": 9,
                    "content": "第二章 上皮组织 上皮细胞 构成 上皮组织。",
                }
            ],
            selected_textbook_ids=["bio-1"],
        )

        node_ids = [node.id for node in graph.nodes]
        self.assertNotIn("bio-1:第二章", node_ids)
        self.assertIn("bio-1:上皮组织", node_ids)


if __name__ == "__main__":
    unittest.main()
