import re
from typing import Any, Protocol

from rank_bm25 import BM25Okapi

from backend.schemas.session import KIBotSession


MAX_RETRIEVED_CHUNKS = 5
BM25_SCORE = 1.0
CHAPTER_SCORE = 2.0
CONCEPT_SCORE = 3.0


class ChatClient(Protocol):
    def chat(self, messages: list[dict[str, Any]]) -> Any:
        ...


def retrieve_chunks(
    session: KIBotSession,
    query: str,
    limit: int = MAX_RETRIEVED_CHUNKS,
) -> list[dict[str, Any]]:
    selected_textbook_ids = _selected_textbook_ids(session.selected_textbooks)
    if not selected_textbook_ids:
        return []

    query_terms = _terms(query)
    query_tokens = _tokens(query)
    query_text = query.casefold()
    concept_names = _matching_concept_names(session.graph_nodes, query_text)

    selected_chunks: list[tuple[int, dict[str, Any]]] = []
    tokenized_corpus: list[list[str]] = []
    for index, raw_chunk in enumerate(session.chunks):
        chunk = _as_dict(raw_chunk)
        if _string_value(chunk, "textbook_id") not in selected_textbook_ids:
            continue

        selected_chunks.append((index, chunk))
        tokenized_corpus.append(_chunk_content_tokens(chunk))

    if not selected_chunks or not query_tokens:
        return []

    bm25_scores = BM25Okapi(tokenized_corpus).get_scores(query_tokens)

    scored: list[tuple[float, int, dict[str, Any], dict[str, Any]]] = []
    for corpus_index, (index, chunk) in enumerate(selected_chunks):
        content = _string_value(chunk, "content")
        chapter = _string_value(chunk, "chapter")

        score = float(bm25_scores[corpus_index]) * BM25_SCORE
        score += _chapter_match_score(query_terms, chapter)
        score += _concept_match_score(concept_names, content, chapter)

        if score <= 0:
            continue

        scored.append((score, index, chunk, _citation_for(chunk)))

    scored.sort(key=lambda item: (-item[0], item[1]))

    results: list[dict[str, Any]] = []
    for rank, (score, _index, chunk, citation) in enumerate(scored[:limit], start=1):
        results.append(
            {
                "rank": rank,
                "score": score,
                "chunk": chunk,
                "citation": citation,
            }
        )
    return results


def answer_query(
    session: KIBotSession,
    question: str,
    llm_client: ChatClient | None = None,
    use_llm: bool = False,
) -> dict[str, Any]:
    retrieved = retrieve_chunks(session, question)
    citations = [result["citation"] for result in retrieved]
    retrieval_status = (
        "ready" if _selected_textbook_ids(session.selected_textbooks) else "no_selected_textbooks"
    )

    if use_llm and llm_client is not None and retrieved:
        try:
            llm_response = llm_client.chat(_rag_messages(question, retrieved))
            answer_text = getattr(llm_response, "answer_text", None)
            if isinstance(answer_text, str) and answer_text.strip():
                _record_token_usage(session, llm_response)
                return {
                    "answer": answer_text.strip(),
                    "answer_source": "llm",
                    "retrieval_status": retrieval_status,
                    "citations": citations,
                    "retrieved_chunks": retrieved,
                }
        except Exception as exc:
            return {
                "answer": _fallback_answer(retrieved),
                "answer_source": "fallback",
                "retrieval_status": retrieval_status,
                "llm_error": _safe_error_message(exc),
                "citations": citations,
                "retrieved_chunks": retrieved,
            }

    return {
        "answer": _fallback_answer(retrieved),
        "answer_source": "fallback",
        "retrieval_status": retrieval_status,
        "citations": citations,
        "retrieved_chunks": retrieved,
    }


def _rag_messages(question: str, retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    context_blocks = []
    for result in retrieved:
        citation = result["citation"]
        chunk = result["chunk"]
        context_blocks.append(
            "\n".join(
                [
                    f"[{result['rank']}] {_citation_label(citation)}",
                    _string_value(chunk, "content"),
                ]
            )
        )

    return [
        {
            "role": "system",
            "content": (
                "Use only the retrieved chunks to answer. Cite every factual claim "
                "with bracketed citation numbers like [1]. If the chunks do not "
                "support an answer, say you do not have enough information."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question: {question.strip()}\n\n"
                "Retrieved chunks:\n"
                + "\n\n".join(context_blocks)
            ),
        },
    ]


def _fallback_answer(retrieved: list[dict[str, Any]]) -> str:
    if not retrieved:
        return "I do not have enough retrieved textbook context to answer this question."

    lines = ["I found these relevant textbook excerpts:"]
    for result in retrieved:
        content = _string_value(result["chunk"], "content")
        excerpt = _compact_excerpt(content)
        lines.append(f"[{result['rank']}] {excerpt}")
    return "\n".join(lines)


def _compact_excerpt(content: str, max_chars: int = 220) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 3].rstrip()}..."


def _chapter_match_score(query_terms: set[str], chapter: str) -> float:
    chapter_terms = _terms(chapter)
    return float(len(query_terms & chapter_terms)) * CHAPTER_SCORE


def _concept_match_score(
    concept_names: list[str],
    content: str,
    chapter: str,
) -> float:
    if not concept_names:
        return 0.0

    searchable = f"{chapter} {content}".casefold()
    matches = sum(1 for name in concept_names if name and name in searchable)
    return float(matches) * CONCEPT_SCORE


def _matching_concept_names(graph_nodes: list[Any], query_text: str) -> list[str]:
    names: list[str] = []
    for node in graph_nodes:
        payload = _as_dict(node)
        name = _string_value(payload, "name") or _string_value(payload, "label")
        normalized = name.strip().casefold()
        if normalized and normalized in query_text:
            names.append(normalized)
    return names


def _terms(text: str) -> set[str]:
    return set(_tokens(text))


def _tokens(text: str) -> list[str]:
    return [
        match.group(0).casefold()
        for match in re.finditer(r"[\w]+", text, flags=re.UNICODE)
        if len(match.group(0)) > 1
    ]


def _chunk_content_tokens(chunk: dict[str, Any]) -> list[str]:
    return _tokens(_string_value(chunk, "content"))


def _selected_textbook_ids(selected_textbooks: list[Any]) -> set[str]:
    ids: set[str] = set()
    for selected in selected_textbooks:
        if isinstance(selected, str) and selected:
            ids.add(selected)
            continue

        payload = _as_dict(selected)
        for key in ("textbook_id", "id"):
            textbook_id = _string_value(payload, key)
            if textbook_id:
                ids.add(textbook_id)
                break
    return ids


def _safe_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        message = exc.__class__.__name__
    secret_prefix = "s" + "k-"
    secret_pattern = rf"{re.escape(secret_prefix)}[A-Za-z0-9_-]+"
    return re.sub(secret_pattern, f"{secret_prefix}REDACTED", message)


def _record_token_usage(session: KIBotSession, llm_response: Any) -> None:
    usage = getattr(llm_response, "token_usage", None)
    if usage is None:
        return
    session.token_usage.calls += _usage_int(usage, "calls")
    session.token_usage.input_tokens += _usage_int(usage, "input_tokens")
    session.token_usage.output_tokens += _usage_int(usage, "output_tokens")
    session.token_usage.total_tokens += _usage_int(usage, "total_tokens")


def _usage_int(usage: Any, field_name: str) -> int:
    value = getattr(usage, field_name, None)
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


def _citation_for(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": chunk.get("chunk_id"),
        "textbook_id": chunk.get("textbook_id"),
        "textbook_title": chunk.get("textbook_title"),
        "chapter": chunk.get("chapter"),
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
    }


def _citation_label(citation: dict[str, Any]) -> str:
    parts = [
        value
        for value in [
            citation.get("textbook_title"),
            citation.get("chapter"),
            _page_label(citation),
        ]
        if value
    ]
    return " - ".join(str(part) for part in parts)


def _page_label(citation: dict[str, Any]) -> str | None:
    page_start = citation.get("page_start")
    page_end = citation.get("page_end")
    if page_start is None and page_end is None:
        return None
    if page_start == page_end or page_end is None:
        return f"p. {page_start}"
    if page_start is None:
        return f"p. {page_end}"
    return f"pp. {page_start}-{page_end}"


def _string_value(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}
