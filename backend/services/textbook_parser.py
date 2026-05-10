import re
from pathlib import Path

import fitz
from docx import Document

from backend.schemas.textbook import FileType, ParsedChapter, ParsedTextbook


SUPPORTED_FILE_TYPES: dict[str, FileType] = {
    ".pdf": "pdf",
    ".txt": "txt",
    ".md": "md",
    ".markdown": "markdown",
    ".docx": "docx",
}
CHAPTER_HEADING_RE = re.compile(r"^第[一二三四五六七八九十百0-9]+[章节]")
FLEXIBLE_CHAPTER_HEADING_RE = re.compile(
    r"^第\s*[一二三四五六七八九十百千万两0-9]+\s*[章节篇]"
)
CHAPTER_PREFIX_RE = re.compile(r"^(第[一二三四五六七八九十百千万两0-9]+[章节篇])")
TOC_CHAPTER_ENTRY_RE = re.compile(
    r"^第\s*[一二三四五六七八九十百千万两0-9]+\s*[章节篇].+\s+\d+\s*$"
)
MEDICAL_TEXTBOOK_TITLES_BY_PREFIX = {
    "01": "局部解剖学",
    "02": "组织学与胚胎学",
    "03": "生理学",
    "04": "医学微生物学",
    "05": "病理学",
    "06": "传染病学",
    "07": "病理生理学",
}


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
    elif file_type == "docx":
        total_pages, total_chars, chapters = _parse_docx(textbook_path)
    else:
        total_pages = 1
        total_text = _read_text_file(textbook_path)
        total_chars = len(total_text)
        chapters = _detect_chapters([total_text], total_pages)

    return ParsedTextbook(
        filename=textbook_path.name,
        title=_infer_textbook_title(textbook_path),
        file_type=file_type,
        file_size_bytes=textbook_path.stat().st_size,
        total_pages=total_pages,
        total_chars=total_chars,
        chapters=chapters,
    )


def _infer_textbook_title(path: Path) -> str:
    stem = path.stem.strip()
    prefix_match = re.match(r"^\s*(0?[1-7])(?:[_\-\s.．、]|$)", stem)
    if prefix_match:
        prefix = prefix_match.group(1).zfill(2)
        return MEDICAL_TEXTBOOK_TITLES_BY_PREFIX[prefix]
    return stem


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


def _parse_docx(path: Path) -> tuple[int, int, list[ParsedChapter]]:
    try:
        document = Document(path)
    except Exception as exc:
        raise ValueError("Invalid DOCX file") from exc

    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    total_text = "\n".join(paragraphs)
    total_chars = len(total_text)
    return 1, total_chars, _detect_chapters([total_text], 1)


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
            if _is_chapter_heading(stripped):
                if self.current_title is not None:
                    self._append_current_chapter()
                else:
                    self.fallback_parts.clear()

                self.current_title = _normalize_chapter_title(stripped)
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


def _is_chapter_heading(text: str) -> bool:
    if _is_toc_chapter_entry(text):
        return False
    return bool(CHAPTER_HEADING_RE.match(text) or FLEXIBLE_CHAPTER_HEADING_RE.match(text))


def _normalize_chapter_title(text: str) -> str:
    title = re.sub(
        r"^第\s*([一二三四五六七八九十百千万两0-9]+)\s*([章节篇])",
        r"第\1\2",
        text.strip(),
    )
    title = re.sub(r"\s+", " ", title).strip()
    prefix_match = CHAPTER_PREFIX_RE.match(title)
    if not prefix_match:
        return title

    prefix = prefix_match.group(1)
    body = title[prefix_match.end() :].strip()
    if not body:
        return prefix

    body = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", body)
    return f"{prefix} {body}"


def _is_toc_chapter_entry(text: str) -> bool:
    return bool(TOC_CHAPTER_ENTRY_RE.match(text.strip()))
