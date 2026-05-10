from collections.abc import Iterator

from backend.schemas.textbook import ParsedTextbook, TextbookChunk


CHUNK_SIZE = 700
CHUNK_OVERLAP = 80


def chunk_textbook(
    textbook: ParsedTextbook,
    *,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[TextbookChunk]:
    if chunk_size <= 0:
        raise ValueError("Chunk size must be positive")
    if overlap < 0:
        raise ValueError("Chunk overlap cannot be negative")
    if overlap >= chunk_size:
        raise ValueError("Chunk overlap must be smaller than chunk size")

    chunks: list[TextbookChunk] = []
    for chapter in textbook.chapters:
        for content in _chunk_content(chapter.content, chunk_size, overlap):
            chunks.append(
                TextbookChunk(
                    textbook_id=textbook.textbook_id,
                    textbook_title=textbook.title,
                    chapter=chapter.title,
                    page_start=chapter.page_start,
                    page_end=chapter.page_end,
                    content=content,
                    char_count=len(content),
                )
            )
    return chunks


def _chunk_content(content: str, chunk_size: int, overlap: int) -> Iterator[str]:
    if not content:
        return

    if len(content) <= chunk_size:
        yield content
        return

    step = chunk_size - overlap
    start = 0
    while start < len(content):
        end = min(start + chunk_size, len(content))
        chunk = content[start:end]
        if chunk:
            yield chunk
        if end == len(content):
            break
        start += step
