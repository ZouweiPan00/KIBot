from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from typing import Any

from backend.schemas.integration import IntegrationAction, IntegrationStats, SankeyData
from backend.schemas.session import KIBotSession


MAX_RATIO = 0.30
MAX_FALLBACK_CONCEPTS_PER_CHUNK = 5

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]{2,12}")
_NON_NAME_RE = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")
_CHAPTER_NAME_RE = re.compile(r"^第[一二三四五六七八九十百千万两0-9]+[章节篇]?$")
_STOPWORDS = {
    "and",
    "are",
    "cell",
    "cells",
    "chapter",
    "content",
    "during",
    "for",
    "from",
    "includes",
    "inside",
    "must",
    "not",
    "should",
    "the",
    "with",
}
_STRUCTURAL_CONCEPTS = {
    "上篇",
    "中篇",
    "下篇",
    "绪论",
    "总论",
    "各论",
    "目录",
    "附录",
    "索引",
    "参考文献",
    "学习目标",
    "复习题",
    "思考题",
}


@dataclass(frozen=True)
class IntegrationResult:
    decisions: list[dict[str, Any]]
    stats: dict[str, Any]
    sankey: dict[str, Any]


@dataclass(frozen=True)
class _Candidate:
    candidate_id: str
    name: str
    textbook_id: str
    textbook_title: str
    chapter: str
    text: str


def run_integration(session: KIBotSession) -> IntegrationResult:
    candidates = _candidate_concepts(session)
    decisions = _build_decisions(candidates)
    stats = _compression_stats(session, decisions)
    sankey = build_sankey(decisions)
    return IntegrationResult(decisions=decisions, stats=stats, sankey=sankey)


def update_decision(
    decisions: list[Any],
    decision_id: str,
    *,
    action: IntegrationAction,
    teacher_note: str,
) -> bool:
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        if decision.get("decision_id") != decision_id:
            continue
        decision["action"] = action
        decision["teacher_note"] = teacher_note
        return True
    return False


def compute_stats(session: KIBotSession, decisions: list[dict[str, Any]]) -> dict[str, Any]:
    return _compression_stats(session, decisions)


def build_sankey(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: list[dict[str, str]] = []
    links: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_links: set[tuple[str, str]] = set()

    for decision in decisions:
        target = f"整合-{decision.get('concept_name') or '概念'}"
        _add_sankey_node(nodes, seen_nodes, target)
        for source in decision.get("sources", []):
            if not isinstance(source, dict):
                continue
            source_name = _source_sankey_name(source)
            _add_sankey_node(nodes, seen_nodes, source_name)
            link_key = (source_name, target)
            if link_key in seen_links:
                continue
            seen_links.add(link_key)
            links.append({"source": source_name, "target": target, "value": 1})

    return SankeyData(nodes=nodes, links=links).model_dump(mode="json")


def _candidate_concepts(session: KIBotSession) -> list[_Candidate]:
    selected_ids = {
        textbook_id
        for textbook_id in session.selected_textbooks
        if isinstance(textbook_id, str)
    }
    if not selected_ids:
        return []

    graph_candidates = _graph_candidates(session.graph_nodes, selected_ids)
    if graph_candidates:
        return graph_candidates
    return _chunk_candidates(session.chunks, selected_ids)


def _graph_candidates(nodes: list[Any], selected_ids: set[str]) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        textbook_id = _textbook_id(node)
        name = str(node.get("name") or "").strip()
        if textbook_id not in selected_ids or not name or _is_structural_concept(name):
            continue
        text = " ".join(
            str(node.get(field) or "")
            for field in ("definition", "explanation", "description", "content")
        )
        candidates.append(
            _Candidate(
                candidate_id=str(node.get("id") or f"{textbook_id}:node:{index}"),
                name=name,
                textbook_id=textbook_id,
                textbook_title=str(node.get("textbook_title") or textbook_id),
                chapter=str(node.get("chapter") or ""),
                text=text,
            )
        )
    return candidates


def _chunk_candidates(chunks: list[Any], selected_ids: set[str]) -> list[_Candidate]:
    grouped: dict[tuple[str, str], _Candidate] = {}
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        textbook_id = _textbook_id(chunk)
        if textbook_id not in selected_ids:
            continue
        text = str(chunk.get("content") or "")
        for key, _count in _extract_concepts(text).most_common(MAX_FALLBACK_CONCEPTS_PER_CHUNK):
            group_key = (textbook_id, _normalize_name(key))
            if group_key in grouped:
                continue
            grouped[group_key] = _Candidate(
                candidate_id=str(chunk.get("chunk_id") or f"{textbook_id}:{key}"),
                name=_display_name(key),
                textbook_id=textbook_id,
                textbook_title=str(chunk.get("textbook_title") or textbook_id),
                chapter=str(chunk.get("chapter") or ""),
                text=text,
            )
    return sorted(grouped.values(), key=lambda item: (item.textbook_id, _normalize_name(item.name)))


def _build_decisions(candidates: list[_Candidate]) -> list[dict[str, Any]]:
    components = _similarity_components(candidates)
    decisions: list[dict[str, Any]] = []
    used_candidate_ids: set[str] = set()

    for component in components:
        textbooks = {candidate.textbook_id for candidate in component}
        if len(component) < 2 or len(textbooks) < 2:
            continue
        used_candidate_ids.update(candidate.candidate_id for candidate in component)
        concept_name = _representative_name(component)
        confidence, reason = _component_confidence_reason(component)
        decisions.append(
            _decision(
                action="merge",
                concept_name=concept_name,
                sources=component,
                reason=reason,
                confidence=confidence,
            )
        )

    for candidate in candidates:
        if candidate.candidate_id in used_candidate_ids:
            continue
        decisions.append(
            _decision(
                action="keep",
                concept_name=candidate.name,
                sources=[candidate],
                reason="unique concept in selected textbooks",
                confidence=0.6,
            )
        )

    return sorted(decisions, key=lambda item: (item["action"] != "merge", item["decision_id"]))


def _similarity_components(candidates: list[_Candidate]) -> list[list[_Candidate]]:
    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_index, left in enumerate(candidates):
        for right_index in range(left_index + 1, len(candidates)):
            right = candidates[right_index]
            if left.textbook_id == right.textbook_id:
                continue
            confidence, _reason = _similarity(left, right)
            if confidence >= 0.7:
                union(left_index, right_index)

    groups: dict[int, list[_Candidate]] = defaultdict(list)
    for index, candidate in enumerate(candidates):
        groups[find(index)].append(candidate)
    return [sorted(group, key=lambda item: (item.textbook_id, item.name)) for group in groups.values()]


def _component_confidence_reason(component: list[_Candidate]) -> tuple[float, str]:
    best_confidence = 0.0
    best_reason = "keyword overlap"
    for left_index, left in enumerate(component):
        for right in component[left_index + 1 :]:
            confidence, reason = _similarity(left, right)
            if confidence > best_confidence:
                best_confidence = confidence
                best_reason = reason
    return round(best_confidence, 2), best_reason


def _similarity(left: _Candidate, right: _Candidate) -> tuple[float, str]:
    left_name = _normalize_name(left.name)
    right_name = _normalize_name(right.name)
    if left_name and left_name == right_name:
        return 0.95, "exact normalized name match"
    if left_name and right_name and (left_name in right_name or right_name in left_name):
        return 0.8, "containment match"

    left_keywords = _keyword_set(f"{left.name} {left.text}")
    right_keywords = _keyword_set(f"{right.name} {right.text}")
    if not left_keywords or not right_keywords:
        return 0.0, "no shared keywords"
    overlap = left_keywords & right_keywords
    score = len(overlap) / max(1, min(len(left_keywords), len(right_keywords)))
    if score >= 0.5:
        return min(0.78, 0.55 + score * 0.35), "keyword overlap in concept explanation"
    return min(0.65, score), "weak keyword overlap"


def _decision(
    *,
    action: IntegrationAction,
    concept_name: str,
    sources: list[_Candidate],
    reason: str,
    confidence: float,
) -> dict[str, Any]:
    source_payloads = [_source_payload(source) for source in sources]
    decision_id = _decision_id(action, concept_name, source_payloads)
    return {
        "decision_id": decision_id,
        "action": action,
        "concept_name": concept_name,
        "sources": source_payloads,
        "reason": reason,
        "confidence": round(confidence, 2),
        "compact_note": _compact_note(action, concept_name, sources),
        "teacher_note": "",
    }


def _compression_stats(session: KIBotSession, decisions: list[dict[str, Any]]) -> dict[str, Any]:
    selected_ids = {
        textbook_id
        for textbook_id in session.selected_textbooks
        if isinstance(textbook_id, str)
    }
    original_chars = sum(
        _textbook_total_chars(textbook)
        for textbook in session.textbooks
        if _textbook_id(textbook) in selected_ids
    )
    compressed_chars = sum(len(str(decision.get("compact_note") or "")) for decision in decisions)
    budget = int(original_chars * MAX_RATIO)
    if original_chars and compressed_chars > budget:
        _apply_note_budget(decisions, budget)
        compressed_chars = sum(len(str(decision.get("compact_note") or "")) for decision in decisions)
    ratio = 0.0 if original_chars <= 0 else compressed_chars / original_chars
    return IntegrationStats(
        original_chars=original_chars,
        compressed_chars=compressed_chars,
        ratio=round(min(ratio, MAX_RATIO), 4),
    ).model_dump(mode="json")


def _apply_note_budget(decisions: list[dict[str, Any]], budget: int) -> None:
    remaining = max(0, budget)
    for decision in decisions:
        note = str(decision.get("compact_note") or "")
        if remaining <= 0:
            decision["compact_note"] = ""
            continue
        decision["compact_note"] = note[:remaining]
        remaining -= len(decision["compact_note"])


def _textbook_total_chars(textbook: Any) -> int:
    if not isinstance(textbook, dict):
        return 0
    textbook_id = _textbook_id(textbook)
    value = textbook.get("total_chars", 0)
    try:
        total_chars = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, total_chars) if textbook_id else 0


def _compact_note(action: IntegrationAction, concept_name: str, sources: list[_Candidate]) -> str:
    titles = "、".join(source.textbook_title for source in sources)
    if action == "merge":
        return f"{concept_name}: integrate overlapping explanations from {titles}."
    return f"{concept_name}: keep as a distinct concept from {titles}."


def _source_payload(source: _Candidate) -> dict[str, Any]:
    return {
        "id": source.candidate_id,
        "name": source.name,
        "textbook_id": source.textbook_id,
        "textbook_title": source.textbook_title,
        "chapter": source.chapter,
    }


def _source_sankey_name(source: dict[str, Any]) -> str:
    title = str(source.get("textbook_title") or source.get("textbook_id") or "")
    name = str(source.get("name") or "")
    return f"{title}-{name}"


def _add_sankey_node(nodes: list[dict[str, str]], seen: set[str], name: str) -> None:
    if name in seen:
        return
    seen.add(name)
    nodes.append({"name": name})


def _decision_id(action: IntegrationAction, concept_name: str, sources: list[dict[str, Any]]) -> str:
    source_key = "-".join(sorted(str(source.get("id") or "") for source in sources))
    slug = _normalize_name(f"{action}-{concept_name}-{source_key}") or "decision"
    return f"integration-{slug[:96]}"


def _representative_name(component: list[_Candidate]) -> str:
    return sorted(component, key=lambda item: (len(item.name), item.name))[0].name


def _extract_concepts(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for match in _WORD_RE.finditer(text):
        key = match.group(0).lower()
        if key not in _STOPWORDS:
            counts[key] += 1
    for match in _CJK_RE.finditer(text):
        key = match.group(0)
        if not _is_structural_concept(key):
            counts[key] += 1
    return counts


def _keyword_set(text: str) -> set[str]:
    return {
        _normalize_name(token)
        for token in _extract_concepts(text)
        if _normalize_name(token)
    }


def _normalize_name(name: str) -> str:
    return _NON_NAME_RE.sub("", name.lower())


def _is_structural_concept(name: str) -> bool:
    stripped = name.strip()
    if not stripped:
        return True
    if stripped in _STRUCTURAL_CONCEPTS:
        return True
    return bool(_CHAPTER_NAME_RE.fullmatch(stripped))


def _display_name(key: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", key):
        return key
    return key.replace("_", " ").title()


def _textbook_id(item: dict[str, Any]) -> str:
    value = item.get("textbook_id", item.get("id"))
    return value if isinstance(value, str) else ""
