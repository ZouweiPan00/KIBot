from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import re
from typing import Any

from backend.schemas.graph import GraphEdge, GraphNode, KnowledgeGraph


MAX_NODES_PER_TEXTBOOK = 30
MAX_VISIBLE_NODES = 150
MIN_TOKEN_LENGTH = 3

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")
_CJK_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,12}")
_CHAPTER_TOKEN_RE = re.compile(r"^第[一二三四五六七八九十百千万两0-9]+[章节篇]?$")
_STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "because",
    "between",
    "chapter",
    "content",
    "for",
    "from",
    "include",
    "includes",
    "into",
    "the",
    "their",
    "these",
    "this",
    "through",
    "use",
    "uses",
    "with",
}
_CJK_STOPWORDS = {
    "第一章",
    "第二章",
    "第三章",
    "第四章",
    "第五章",
    "第六章",
    "第七章",
    "第八章",
    "第九章",
    "第十章",
    "第一节",
    "第二节",
    "第三节",
    "目录",
    "教材",
    "内容",
    "章节",
    "本章",
    "学习目标",
    "复习题",
}


@dataclass
class _ConceptStats:
    key: str
    name: str
    textbook_id: str
    textbook_title: str
    chapter: str
    page: int
    frequency: int = 0
    chunk_count: int = 0


def build_knowledge_graph(
    chunks: list[dict[str, Any]],
    *,
    selected_textbook_ids: list[str] | None = None,
    llm_client: Any | None = None,
    use_ai: bool = False,
) -> KnowledgeGraph:
    selected_ids = set(selected_textbook_ids or [])
    selected_chunks = [
        chunk
        for chunk in chunks
        if not selected_ids or _chunk_textbook_id(chunk) in selected_ids
    ]
    if use_ai and llm_client is not None:
        ai_graph = build_ai_knowledge_graph(selected_chunks, llm_client)
        if ai_graph is not None:
            return ai_graph

    return _build_deterministic_graph(selected_chunks)


def build_ai_knowledge_graph(
    selected_chunks: list[dict[str, Any]],
    llm_client: Any,
) -> KnowledgeGraph | None:
    try:
        response = _call_llm_client(llm_client, _graph_prompt(selected_chunks))
        payload = _parse_ai_payload(response)
        return _validated_ai_graph(payload)
    except (TypeError, ValueError, AttributeError, KeyError):
        return None


def _build_deterministic_graph(selected_chunks: list[dict[str, Any]]) -> KnowledgeGraph:
    concept_stats: dict[tuple[str, str], _ConceptStats] = {}
    pair_counts: Counter[tuple[str, str]] = Counter()

    for chunk in selected_chunks:
        textbook_id = _chunk_textbook_id(chunk)
        if not textbook_id:
            continue

        token_counts = _extract_concepts(_concept_source_text(chunk))
        if not token_counts:
            continue

        chunk_node_ids: list[str] = []
        for key, count in token_counts.items():
            stats_key = (textbook_id, key)
            if stats_key not in concept_stats:
                concept_stats[stats_key] = _ConceptStats(
                    key=key,
                    name=_display_name(key),
                    textbook_id=textbook_id,
                    textbook_title=str(chunk.get("textbook_title") or ""),
                    chapter=str(chunk.get("chapter") or ""),
                    page=_chunk_page(chunk),
                )
            stats = concept_stats[stats_key]
            stats.frequency += count
            stats.chunk_count += 1
            chunk_node_ids.append(_node_id(textbook_id, key))

        for index, source in enumerate(sorted(set(chunk_node_ids))):
            for target in sorted(set(chunk_node_ids))[index + 1 :]:
                pair_counts[(source, target)] += 1

    nodes = _visible_nodes(concept_stats.values())
    visible_node_ids = {node.id for node in nodes}
    edges = _visible_edges(pair_counts, visible_node_ids, nodes)
    return KnowledgeGraph(nodes=nodes, edges=edges)


def _call_llm_client(llm_client: Any, prompt: str) -> Any:
    if callable(llm_client):
        return llm_client(prompt)
    if hasattr(llm_client, "complete"):
        return llm_client.complete(prompt)
    if hasattr(llm_client, "generate"):
        return llm_client.generate(prompt)
    raise TypeError("LLM client must be callable or expose complete/generate")


def _graph_prompt(selected_chunks: list[dict[str, Any]]) -> str:
    schema = {
        "nodes": [
            {
                "name": "",
                "definition": "",
                "category": "concept",
                "textbook_id": "",
                "textbook_title": "",
                "chapter": "",
                "page": 1,
                "frequency": 1,
                "importance": 1.0,
            }
        ],
        "edges": [
            {
                "source": "",
                "target": "",
                "relation_type": "related_to",
                "description": "",
                "confidence": 0.5,
            }
        ],
    }
    chunk_payload = []
    for chunk in selected_chunks[:20]:
        chunk_payload.append(
            {
                "textbook_id": _chunk_textbook_id(chunk),
                "textbook_title": str(chunk.get("textbook_title") or ""),
                "chapter": str(chunk.get("chapter") or ""),
                "page": _chunk_page(chunk),
                "content": _concept_source_text(chunk)[:2000],
            }
        )
    return (
        "Extract a textbook knowledge graph from these chunks. "
        "Return only JSON matching this schema example: "
        f"{json.dumps(schema, ensure_ascii=False)}. "
        f"Chunks: {json.dumps(chunk_payload, ensure_ascii=False)}"
    )


def _parse_ai_payload(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response

    content = response
    if hasattr(response, "content"):
        content = response.content
    elif isinstance(response, list) and response:
        content = response[0]
    elif hasattr(response, "choices") and response.choices:
        choice = response.choices[0]
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None) or getattr(choice, "text", None)

    if not isinstance(content, str):
        raise TypeError("AI response content must be JSON text or a dict")

    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("AI response must be a JSON object")
    return parsed


def _validated_ai_graph(payload: dict[str, Any]) -> KnowledgeGraph:
    raw_nodes = payload.get("nodes")
    raw_edges = payload.get("edges")
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise ValueError("AI graph requires nodes and edges lists")

    nodes = [_ai_node(item) for item in raw_nodes]
    if not nodes:
        raise ValueError("AI graph requires at least one node")

    nodes = _limit_ai_nodes(nodes)
    node_ids = {node.id for node in nodes}
    name_to_id = {node.name.strip().lower(): node.id for node in nodes}
    visible_edges = [_ai_edge(item, node_ids, name_to_id) for item in raw_edges]
    return KnowledgeGraph(nodes=sorted(nodes, key=lambda node: node.id), edges=visible_edges)


def _ai_node(item: Any) -> GraphNode:
    if not isinstance(item, dict):
        raise ValueError("AI node must be an object")

    name = _required_string(item, "name")
    textbook_id = _required_string(item, "textbook_id")
    key = str(item.get("id") or name).lower()
    node_id = str(item.get("id") or _node_id(textbook_id, key))
    return GraphNode(
        id=node_id,
        name=name,
        definition=_required_string(item, "definition"),
        category=str(item.get("category") or "concept"),
        textbook_id=textbook_id,
        textbook_title=str(item.get("textbook_title") or ""),
        chapter=str(item.get("chapter") or ""),
        page=_coerce_int(item.get("page"), default=1),
        frequency=max(1, _coerce_int(item.get("frequency"), default=1)),
        importance=_coerce_float(item.get("importance"), default=1.0),
        status="active",
    )


def _ai_edge(
    item: Any,
    node_ids: set[str],
    name_to_id: dict[str, str],
) -> GraphEdge:
    if not isinstance(item, dict):
        raise ValueError("AI edge must be an object")

    source = _resolve_ai_node_ref(_required_string(item, "source"), node_ids, name_to_id)
    target = _resolve_ai_node_ref(_required_string(item, "target"), node_ids, name_to_id)
    relation_type = str(item.get("relation_type") or "related_to")
    return GraphEdge(
        id=str(item.get("id") or f"{source}->{target}:{relation_type}"),
        source=source,
        target=target,
        relation_type=relation_type,
        description=_required_string(item, "description"),
        confidence=_coerce_float(item.get("confidence"), default=0.5),
    )


def _limit_ai_nodes(nodes: list[GraphNode]) -> list[GraphNode]:
    by_textbook: dict[str, list[GraphNode]] = defaultdict(list)
    for node in nodes:
        by_textbook[node.textbook_id].append(node)

    candidates: list[GraphNode] = []
    for textbook_id in sorted(by_textbook):
        ranked = sorted(
            by_textbook[textbook_id],
            key=lambda node: (-node.importance, node.name.lower(), node.id),
        )[:MAX_NODES_PER_TEXTBOOK]
        candidates.extend(ranked)

    return sorted(
        candidates,
        key=lambda node: (-node.importance, node.textbook_id, node.id),
    )[:MAX_VISIBLE_NODES]


def _required_string(item: dict[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"AI field {field} must be a non-empty string")
    return value.strip()


def _resolve_ai_node_ref(
    value: str,
    node_ids: set[str],
    name_to_id: dict[str, str],
) -> str:
    if value in node_ids:
        return value
    resolved = name_to_id.get(value.strip().lower())
    if resolved is None:
        raise ValueError("AI edge references an unknown node")
    return resolved


def _coerce_int(value: Any, *, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError("AI integer field is invalid") from None


def _coerce_float(value: Any, *, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError("AI float field is invalid") from None


def _extract_concepts(content: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for match in _TOKEN_RE.finditer(content):
        token = match.group(0)
        key = token.lower()
        if len(key) < MIN_TOKEN_LENGTH or key in _STOPWORDS:
            continue
        counts[key] += 1
    for match in _CJK_TOKEN_RE.finditer(content):
        key = _clean_cjk_concept(match.group(0))
        if key:
            counts[key] += 1
    return counts


def _concept_source_text(chunk: dict[str, Any]) -> str:
    return str(chunk.get("content") or "")


def _visible_nodes(stats: Any) -> list[GraphNode]:
    by_textbook: dict[str, list[_ConceptStats]] = defaultdict(list)
    for item in stats:
        by_textbook[item.textbook_id].append(item)

    candidates: list[GraphNode] = []
    for textbook_id in sorted(by_textbook):
        ranked = sorted(
            by_textbook[textbook_id],
            key=lambda item: (-item.frequency, item.key),
        )[:MAX_NODES_PER_TEXTBOOK]
        candidates.extend(_to_node(item) for item in ranked)

    limited = sorted(
        candidates,
        key=lambda node: (-node.importance, node.textbook_id, node.id),
    )[:MAX_VISIBLE_NODES]
    return sorted(limited, key=lambda node: node.id)


def _visible_edges(
    pair_counts: Counter[tuple[str, str]],
    visible_node_ids: set[str],
    nodes: list[GraphNode],
) -> list[GraphEdge]:
    node_names = {node.id: node.name for node in nodes}
    edges: list[GraphEdge] = []
    for (source, target), count in sorted(pair_counts.items()):
        if source not in visible_node_ids or target not in visible_node_ids:
            continue
        confidence = min(0.95, 0.45 + (count * 0.1))
        edges.append(
            GraphEdge(
                id=f"{source}->{target}:co_occurs",
                source=source,
                target=target,
                relation_type="co_occurs",
                description=(
                    f"{node_names[source]} appears with {node_names[target]} "
                    "in the selected textbook chunks."
                ),
                confidence=round(confidence, 2),
            )
        )
    return edges


def _to_node(stats: _ConceptStats) -> GraphNode:
    importance = round(stats.frequency + (stats.chunk_count * 0.25), 2)
    return GraphNode(
        id=_node_id(stats.textbook_id, stats.key),
        name=stats.name,
        definition=(
            f"{stats.name} is a concept found in {stats.chapter} "
            f"from {stats.textbook_title}."
        ),
        category="concept",
        textbook_id=stats.textbook_id,
        textbook_title=stats.textbook_title,
        chapter=stats.chapter,
        page=stats.page,
        frequency=stats.frequency,
        importance=importance,
        status="active",
    )


def _node_id(textbook_id: str, key: str) -> str:
    slug = re.sub(r"[^a-z0-9_\u4e00-\u9fff]+", "-", key).strip("-")
    return f"{textbook_id}:{slug}"


def _display_name(key: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", key):
        return key
    return key.replace("_", " ").title()


def _clean_cjk_concept(value: str) -> str:
    key = value.strip()
    key = re.sub(r"^第[一二三四五六七八九十百千万两0-9]+[章节篇]", "", key)
    if len(key) < 2:
        return ""
    if key in _CJK_STOPWORDS or _CHAPTER_TOKEN_RE.match(key):
        return ""
    if re.fullmatch(r"[一二三四五六七八九十百千万两0-9]+", key):
        return ""
    return key


def _chunk_textbook_id(chunk: dict[str, Any]) -> str:
    value = chunk.get("textbook_id")
    return value if isinstance(value, str) else ""


def _chunk_page(chunk: dict[str, Any]) -> int:
    value = chunk.get("page_start", chunk.get("page", 1))
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1
