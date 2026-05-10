from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


FileType = Literal["pdf", "txt", "md", "markdown"]


def _new_id() -> str:
    return str(uuid4())


class ParsedChapter(BaseModel):
    chapter_id: str = Field(default_factory=_new_id)
    title: str
    page_start: int = 1
    page_end: int = 1
    content: str
    char_count: int


class ParsedTextbook(BaseModel):
    textbook_id: str = Field(default_factory=_new_id)
    filename: str
    title: str
    file_type: FileType
    total_pages: int = 0
    total_chars: int = 0
    chapters: list[ParsedChapter] = Field(default_factory=list)
    status: Literal["parsed"] = "parsed"
