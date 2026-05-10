from collections import Counter, defaultdict
from dataclasses import dataclass
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
) -> KnowledgeGraph:
    selected_ids = set(selected_textbook_ids or [])
    selected_chunks = [
        chunk
        for chunk in chunks
        if not selected_ids or _chunk_textbook_id(chunk) in selected_ids
    ]

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
