import sys
import tempfile
import unittest
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TextbookParserTest(unittest.TestCase):
    def test_parse_txt_detects_chinese_chapters(self) -> None:
        from backend.services.textbook_parser import parse_textbook

        content = "导言\n第一章 细胞\n细胞是生命的基本单位。\n第二节 结构\n细胞膜保护细胞。\n第2章 遗传\nDNA 携带遗传信息。"

        with tempfile.TemporaryDirectory() as temp_dir:
            textbook_path = Path(temp_dir) / "biology.txt"
            textbook_path.write_text(content, encoding="utf-8")

            parsed = parse_textbook(textbook_path)

        UUID(parsed.textbook_id)
        self.assertEqual(parsed.filename, "biology.txt")
        self.assertEqual(parsed.title, "biology")
        self.assertEqual(parsed.file_type, "txt")
        self.assertEqual(parsed.total_pages, 1)
        self.assertEqual(parsed.total_chars, len(content))
        self.assertEqual(parsed.status, "parsed")
        self.assertEqual(
            [chapter.title for chapter in parsed.chapters],
            ["第一章 细胞", "第二节 结构", "第2章 遗传"],
        )
        self.assertTrue(parsed.chapters[0].content.startswith("第一章 细胞"))
        self.assertNotIn("导言", parsed.chapters[0].content)
        self.assertEqual(parsed.chapters[0].page_start, 1)
        self.assertEqual(parsed.chapters[0].page_end, 1)
        self.assertEqual(
            [chapter.char_count for chapter in parsed.chapters],
            [len(chapter.content) for chapter in parsed.chapters],
        )

    def test_parse_txt_detects_pdf_extracted_spaced_chapter_headings(self) -> None:
        from backend.services.textbook_parser import parse_textbook

        content = "目录\n第 一 章 细胞\n细胞内容。\n第 2 节 结构\n结构内容。"

        with tempfile.TemporaryDirectory() as temp_dir:
            textbook_path = Path(temp_dir) / "02__textbook.txt"
            textbook_path.write_text(content, encoding="utf-8")

            parsed = parse_textbook(textbook_path)

        self.assertEqual(parsed.title, "组织学与胚胎学")
        self.assertEqual(
            [chapter.title for chapter in parsed.chapters],
            ["第一章 细胞", "第2节 结构"],
        )

    def test_parse_txt_ignores_toc_entries_and_normalizes_spaced_heading_title(
        self,
    ) -> None:
        from backend.services.textbook_parser import parse_textbook

        content = (
            "目录\n"
            "第 一 章  绪 论  1\n"
            "第 二 章  上 皮 组 织  12\n"
            "第 三 章  结 缔 组 织  28\n"
            "\n"
            "第 二 章  上 皮 组 织\n"
            "上皮组织由密集排列的上皮细胞和少量细胞外基质构成。\n"
            "第 三 章  结 缔 组 织\n"
            "结缔组织包括细胞和大量细胞外基质。\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            textbook_path = Path(temp_dir) / "histology.txt"
            textbook_path.write_text(content, encoding="utf-8")

            parsed = parse_textbook(textbook_path)

        self.assertEqual(
            [chapter.title for chapter in parsed.chapters],
            ["第二章 上皮组织", "第三章 结缔组织"],
        )
        self.assertNotIn("目录", parsed.chapters[0].content)
        self.assertNotIn("第 一 章", parsed.chapters[0].content)

    def test_parse_markdown_without_heading_falls_back_to_full_text(self) -> None:
        from backend.services.textbook_parser import parse_textbook

        content = "# Notes\n\nNo Chinese chapter headings here."

        with tempfile.TemporaryDirectory() as temp_dir:
            textbook_path = Path(temp_dir) / "notes.md"
            textbook_path.write_text(content, encoding="utf-8")

            parsed = parse_textbook(textbook_path)

        self.assertEqual(parsed.filename, "notes.md")
        self.assertEqual(parsed.file_type, "md")
        self.assertEqual(parsed.total_pages, 1)
        self.assertEqual(len(parsed.chapters), 1)
        self.assertEqual(parsed.chapters[0].title, "全文")
        self.assertEqual(parsed.chapters[0].content, content)
        self.assertEqual(parsed.chapters[0].char_count, len(content))

    def test_parse_txt_uses_gb18030_fallback_before_replacement(self) -> None:
        from backend.services.textbook_parser import parse_textbook

        content = "第一章 编码\n中文内容可以被完整读取。"

        with tempfile.TemporaryDirectory() as temp_dir:
            textbook_path = Path(temp_dir) / "gb-text.txt"
            textbook_path.write_bytes(content.encode("gb18030"))

            parsed = parse_textbook(textbook_path)

        self.assertEqual(parsed.total_chars, len(content))
        self.assertIn("中文内容", parsed.chapters[0].content)
        self.assertNotIn("\ufffd", parsed.chapters[0].content)

    def test_parse_txt_preserves_gb18030_text_when_replacing_invalid_tail(self) -> None:
        from backend.services.textbook_parser import parse_textbook

        valid_gb18030 = "第一章 编码".encode("gb18030")

        with tempfile.TemporaryDirectory() as temp_dir:
            textbook_path = Path(temp_dir) / "mixed-gb-text.txt"
            textbook_path.write_bytes(valid_gb18030 + b"\xff")

            parsed = parse_textbook(textbook_path)

        self.assertEqual(parsed.total_chars, len("第一章 编码\ufffd"))
        self.assertEqual(parsed.chapters[0].title, "第一章 编码\ufffd")
        self.assertEqual(parsed.chapters[0].content, "第一章 编码\ufffd")

    def test_parse_pdf_extracts_pages_and_chapter_page_ranges(self) -> None:
        import fitz

        from backend.services.textbook_parser import parse_textbook

        with tempfile.TemporaryDirectory() as temp_dir:
            textbook_path = Path(temp_dir) / "lesson.pdf"
            document = fitz.open()
            first_page = document.new_page()
            first_page.insert_text(
                (72, 72),
                "第一章 PDF\n第一页内容",
                fontname="china-s",
            )
            second_page = document.new_page()
            second_page.insert_text(
                (72, 72),
                "第二章 继续\n第二页内容",
                fontname="china-s",
            )
            document.save(textbook_path)
            document.close()

            parsed = parse_textbook(textbook_path)

        self.assertEqual(parsed.filename, "lesson.pdf")
        self.assertEqual(parsed.file_type, "pdf")
        self.assertEqual(parsed.total_pages, 2)
        self.assertEqual(
            [chapter.title for chapter in parsed.chapters],
            ["第一章 PDF", "第二章 继续"],
        )
        self.assertEqual(parsed.chapters[0].page_start, 1)
        self.assertEqual(parsed.chapters[0].page_end, 1)
        self.assertEqual(parsed.chapters[1].page_start, 2)
        self.assertEqual(parsed.chapters[1].page_end, 2)
        self.assertIn("第一页内容", parsed.chapters[0].content)
        self.assertIn("第二页内容", parsed.chapters[1].content)

    def test_parse_pdf_rejects_corrupt_pdf_as_value_error(self) -> None:
        from backend.services.textbook_parser import parse_textbook

        with tempfile.TemporaryDirectory() as temp_dir:
            textbook_path = Path(temp_dir) / "broken.pdf"
            textbook_path.write_bytes(b"not a pdf")

            with self.assertRaises(ValueError):
                parse_textbook(textbook_path)

    def test_parse_rejects_unsupported_file_type(self) -> None:
        from backend.services.textbook_parser import parse_textbook

        with tempfile.TemporaryDirectory() as temp_dir:
            textbook_path = Path(temp_dir) / "slides.docx"
            textbook_path.write_text("not supported", encoding="utf-8")

            with self.assertRaises(ValueError):
                parse_textbook(textbook_path)


if __name__ == "__main__":
    unittest.main()
