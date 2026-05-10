import re
from pathlib import Path

import fitz

from backend.schemas.textbook import FileType, ParsedChapter, ParsedTextbook


SUPPORTED_FILE_TYPES: dict[str, FileType] = {
    ".pdf": "pdf",
    ".txt": "txt",
    ".md": "md",
    ".markdown": "markdown",
}
CHAPTER_HEADING_RE = re.compile(r"^第[一二三四五六七八九十百0-9]+[章节]")


def get_file_type(filename: str | Path) -> FileType:
    suffix = Path(filename).suffix.lower()
    try:
        return SUPPORTED_FILE_TYPES[suffix]
    except KeyError as exc:
        raise ValueError("Unsupported textbook file type") from exc


def parse_textbook(path: str | Path) -> ParsedTextbook:
    textbook_path = Path(path)
    file_type = get_file_type(textbook_path)

    if file_type == "pdf":
        total_pages, total_chars, chapters = _parse_pdf(textbook_path)
    else:
        total_pages = 1
        total_text = _read_text_file(textbook_path)
        total_chars = len(total_text)
        chapters = _detect_chapters([total_text], total_pages)

    return ParsedTextbook(
        filename=textbook_path.name,
        title=textbook_path.stem,
        file_type=file_type,
        total_pages=total_pages,
        total_chars=total_chars,
        chapters=chapters,
    )


def _read_text_file(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("gb18030", errors="replace")


def _parse_pdf(path: Path) -> tuple[int, int, list[ParsedChapter]]:
    try:
        document = fitz.open(path)
    except (fitz.FileDataError, ValueError) as exc:
        raise ValueError("Invalid PDF file") from exc

    collector = _ChapterCollector()
    total_chars = 0
    try:
        total_pages = document.page_count
        for page_index, page in enumerate(document, start=1):
            try:
                page_text = page.get_text()
            except (RuntimeError, ValueError) as exc:
                raise ValueError("Invalid PDF file") from exc
            total_chars += len(page_text)
            collector.add_page(page_text, page_index)
    finally:
        document.close()

    return total_pages, total_chars, collector.finish(total_pages)


def _detect_chapters(page_texts: list[str], total_pages: int) -> list[ParsedChapter]:
    collector = _ChapterCollector()
    for page_index, page_text in enumerate(page_texts, start=1):
        collector.add_page(page_text, page_index)
    return collector.finish(total_pages)


class _ChapterCollector:
    def __init__(self) -> None:
        self.chapters: list[ParsedChapter] = []
        self.current_title: str | None = None
        self.current_start_page = 1
        self.current_end_page = 1
        self.current_lines: list[str] = []
        self.fallback_parts: list[str] = []

    def add_page(self, page_text: str, page_index: int) -> None:
        if self.current_title is None and not self.chapters:
            self.fallback_parts.append(page_text)

        for line in page_text.splitlines(keepends=True):
            stripped = line.strip()
            if CHAPTER_HEADING_RE.match(stripped):
                if self.current_title is not None:
                    self._append_current_chapter()
                else:
                    self.fallback_parts.clear()

                self.current_title = stripped
                self.current_start_page = page_index
                self.current_end_page = page_index
                self.current_lines = [line]
                continue

            if self.current_title is not None:
                self.current_lines.append(line)
                self.current_end_page = page_index

    def finish(self, total_pages: int) -> list[ParsedChapter]:
        if self.current_title is not None:
            self._append_current_chapter()
            self.current_title = None

        if self.chapters:
            return self.chapters

        page_end = total_pages if total_pages > 0 else 1
        return [
            _make_chapter(
                title="全文",
                page_start=1,
                page_end=page_end,
                content="".join(self.fallback_parts),
            )
        ]

    def _append_current_chapter(self) -> None:
        if self.current_title is None:
            return

        self.chapters.append(
            _make_chapter(
                title=self.current_title,
                page_start=self.current_start_page,
                page_end=self.current_end_page,
                content="".join(self.current_lines),
            )
        )


def _make_chapter(
    *,
    title: str,
    page_start: int,
    page_end: int,
    content: str,
) -> ParsedChapter:
    return ParsedChapter(
        title=title,
        page_start=page_start,
        page_end=page_end,
        content=content,
        char_count=len(content),
    )
