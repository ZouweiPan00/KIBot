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
        page_texts = _read_pdf_pages(textbook_path)
    else:
        page_texts = [_read_text_file(textbook_path)]

    total_pages = len(page_texts) if file_type == "pdf" else 1
    total_text = "".join(page_texts)
    chapters = _detect_chapters(page_texts, total_pages)

    return ParsedTextbook(
        filename=textbook_path.name,
        title=textbook_path.stem,
        file_type=file_type,
        total_pages=total_pages,
        total_chars=len(total_text),
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


def _read_pdf_pages(path: Path) -> list[str]:
    document = fitz.open(path)
    try:
        return [page.get_text() for page in document]
    finally:
        document.close()


def _detect_chapters(page_texts: list[str], total_pages: int) -> list[ParsedChapter]:
    chapters: list[ParsedChapter] = []
    current_title: str | None = None
    current_start_page = 1
    current_end_page = 1
    current_lines: list[str] = []

    for page_index, page_text in enumerate(page_texts, start=1):
        for line in page_text.splitlines(keepends=True):
            stripped = line.strip()
            if CHAPTER_HEADING_RE.match(stripped):
                if current_title is not None:
                    chapters.append(
                        _make_chapter(
                            title=current_title,
                            page_start=current_start_page,
                            page_end=current_end_page,
                            content="".join(current_lines),
                        )
                    )

                current_title = stripped
                current_start_page = page_index
                current_end_page = page_index
                current_lines = [line]
                continue

            if current_title is not None:
                current_lines.append(line)
                current_end_page = page_index

    if current_title is not None:
        chapters.append(
            _make_chapter(
                title=current_title,
                page_start=current_start_page,
                page_end=current_end_page,
                content="".join(current_lines),
            )
        )

    if chapters:
        return chapters

    full_text = "".join(page_texts)
    page_end = total_pages if total_pages > 0 else 1
    return [
        _make_chapter(
            title="全文",
            page_start=1,
            page_end=page_end,
            content=full_text,
        )
    ]


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
