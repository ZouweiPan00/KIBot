import sys
import unittest
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class ChunkerTest(unittest.TestCase):
    def test_short_chapter_produces_one_chunk_with_metadata(self) -> None:
        from backend.schemas.textbook import ParsedChapter, ParsedTextbook
        from backend.services.chunker import chunk_textbook

        content = "第一章 开始\n这是一段短教材内容。"
        parsed = ParsedTextbook(
            textbook_id="book-1",
            filename="biology.txt",
            title="biology",
            file_type="txt",
            total_pages=3,
            total_chars=len(content),
            chapters=[
                ParsedChapter(
                    title="第一章 开始",
                    page_start=2,
                    page_end=3,
                    content=content,
                    char_count=len(content),
                )
            ],
        )

        chunks = chunk_textbook(parsed)

        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]
        UUID(chunk.chunk_id)
        self.assertEqual(chunk.textbook_id, "book-1")
        self.assertEqual(chunk.textbook_title, "biology")
        self.assertEqual(chunk.chapter, "第一章 开始")
        self.assertEqual(chunk.page_start, 2)
        self.assertEqual(chunk.page_end, 3)
        self.assertEqual(chunk.content, content)
        self.assertEqual(chunk.char_count, len(content))

    def test_long_chapter_produces_overlapping_chunks_with_max_size(self) -> None:
        from backend.schemas.textbook import ParsedChapter, ParsedTextbook
        from backend.services.chunker import chunk_textbook

        content = "".join(chr(0x4E00 + index) for index in range(1500))
        parsed = ParsedTextbook(
            textbook_id="book-2",
            filename="long.txt",
            title="long",
            file_type="txt",
            total_pages=1,
            total_chars=len(content),
            chapters=[
                ParsedChapter(
                    title="第一章 长文本",
                    page_start=1,
                    page_end=1,
                    content=content,
                    char_count=len(content),
                )
            ],
        )

        chunks = chunk_textbook(parsed)

        self.assertEqual(len(chunks), 3)
        self.assertTrue(all(0 < len(chunk.content) <= 700 for chunk in chunks))
        self.assertEqual(chunks[0].content, content[:700])
        self.assertEqual(chunks[1].content, content[620:1320])
        self.assertEqual(chunks[2].content, content[1240:])
        self.assertEqual(chunks[0].content[-80:], chunks[1].content[:80])
        self.assertEqual(chunks[1].content[-80:], chunks[2].content[:80])
        self.assertEqual(
            [chunk.char_count for chunk in chunks],
            [len(chunk.content) for chunk in chunks],
        )

    def test_empty_chapter_content_does_not_create_empty_chunks(self) -> None:
        from backend.schemas.textbook import ParsedChapter, ParsedTextbook
        from backend.services.chunker import chunk_textbook

        parsed = ParsedTextbook(
            textbook_id="book-3",
            filename="empty.txt",
            title="empty",
            file_type="txt",
            chapters=[
                ParsedChapter(
                    title="第一章 空白",
                    page_start=1,
                    page_end=1,
                    content="",
                    char_count=0,
                )
            ],
        )

        self.assertEqual(chunk_textbook(parsed), [])


if __name__ == "__main__":
    unittest.main()
