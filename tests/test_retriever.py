import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class RetrieverTest(unittest.TestCase):
    def session(self):
        from backend.schemas.session import KIBotSession

        session = KIBotSession(session_id="00000000-0000-0000-0000-000000000001")
        session.graph_nodes.extend(
            [
                {"node_id": "concept-atp", "name": "ATP"},
                {"node_id": "concept-osmosis", "label": "Osmosis"},
            ]
        )
        session.chunks.extend(
            [
                {
                    "chunk_id": "c-atp",
                    "textbook_id": "book-bio",
                    "textbook_title": "Biology",
                    "chapter": "Cellular Respiration",
                    "page_start": 7,
                    "page_end": 8,
                    "content": "ATP stores energy for cells during respiration.",
                },
                {
                    "chunk_id": "c-chapter",
                    "textbook_id": "book-bio",
                    "textbook_title": "Biology",
                    "chapter": "Respiration Overview",
                    "page_start": 9,
                    "page_end": 9,
                    "content": "Glucose is broken down in stages.",
                },
                {
                    "chunk_id": "c-concept",
                    "textbook_id": "book-bio",
                    "textbook_title": "Biology",
                    "chapter": "Membranes",
                    "page_start": 15,
                    "page_end": 16,
                    "content": "Water movement depends on concentration gradients.",
                },
                {
                    "chunk_id": "c-none",
                    "textbook_id": "book-chem",
                    "textbook_title": "Chemistry",
                    "chapter": "Atoms",
                    "page_start": 1,
                    "page_end": 1,
                    "content": "Protons and electrons form atoms.",
                },
            ]
        )
        return session

    def test_retrieve_chunks_scores_terms_concepts_and_chapters_with_citations(self) -> None:
        from backend.services.retriever import retrieve_chunks

        results = retrieve_chunks(self.session(), "How does ATP respiration work?")

        self.assertEqual([result["chunk"]["chunk_id"] for result in results], ["c-atp", "c-chapter"])
        self.assertGreater(results[0]["score"], results[1]["score"])
        self.assertEqual(
            results[0]["citation"],
            {
                "chunk_id": "c-atp",
                "textbook_id": "book-bio",
                "textbook_title": "Biology",
                "chapter": "Cellular Respiration",
                "page_start": 7,
                "page_end": 8,
            },
        )

    def test_retrieve_chunks_limits_to_top_five_deterministically(self) -> None:
        from backend.services.retriever import retrieve_chunks

        session = self.session()
        for index in range(8):
            session.chunks.append(
                {
                    "chunk_id": f"extra-{index}",
                    "chapter": "Respiration",
                    "content": f"respiration detail {index}",
                }
            )

        results = retrieve_chunks(session, "respiration", limit=5)

        self.assertEqual(len(results), 5)
        self.assertEqual(results[0]["chunk"]["chunk_id"], "c-atp")
        self.assertEqual([result["rank"] for result in results], [1, 2, 3, 4, 5])

    def test_answer_query_uses_llm_with_strict_citation_prompt(self) -> None:
        from backend.services.retriever import answer_query

        calls = []

        class FakeLLM:
            def chat(self, messages):
                calls.append(messages)
                return SimpleNamespace(answer_text="ATP stores usable cell energy. [1]")

        response = answer_query(self.session(), "What is ATP?", llm_client=FakeLLM())

        self.assertEqual(response["answer"], "ATP stores usable cell energy. [1]")
        self.assertEqual(response["citations"][0]["chunk_id"], "c-atp")
        self.assertIn("Use only the retrieved chunks", calls[0][0]["content"])
        self.assertIn("[1]", calls[0][1]["content"])
        self.assertIn("Cellular Respiration", calls[0][1]["content"])

    def test_answer_query_falls_back_to_template_when_llm_missing_or_fails(self) -> None:
        from backend.services.retriever import answer_query

        class BrokenLLM:
            def chat(self, messages):
                raise RuntimeError("provider unavailable")

        missing = answer_query(self.session(), "What is ATP?", llm_client=None)
        failed = answer_query(self.session(), "What is ATP?", llm_client=BrokenLLM())

        self.assertEqual(missing["answer"], failed["answer"])
        self.assertIn("[1]", missing["answer"])
        self.assertIn("ATP stores energy", missing["answer"])
        self.assertEqual(missing["citations"][0]["chunk_id"], "c-atp")


if __name__ == "__main__":
    unittest.main()
