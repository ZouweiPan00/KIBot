from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from typing import Any

from backend.schemas.integration import IntegrationAction, IntegrationStats, SankeyData
from backend.schemas.session import KIBotSession


TARGET_RATIO = 0.25
MAX_RATIO = 0.30
MAX_CANDIDATES = 240
MAX_CANDIDATES_PER_TEXTBOOK = 60
MAX_DECISIONS = 80
MAX_SOURCES_PER_DECISION = 8
MAX_SANKEY_LINKS = 120
MAX_SANKEY_NODES = 200
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
        if len(links) >= MAX_SANKEY_LINKS:
            break
        target = f"整合-{decision.get('concept_name') or '概念'}"
        if not _add_sankey_node(nodes, seen_nodes, target):
            break
        for source in decision.get("sources", []):
            if len(links) >= MAX_SANKEY_LINKS:
                break
            if not isinstance(source, dict):
                continue
            source_name = _source_sankey_name(source)
            if not _add_sankey_node(nodes, seen_nodes, source_name):
                break
            link_key = (source_name, target)
            if link_key in seen_links:
                continue
            seen_links.add(link_key)
            links.append({"source": source_name, "target": target, "value": 1})

    return SankeyData(nodes=nodes, links=links).model_dump(mode="json")


def _candidate_concepts(session: KIBotSession) -> list[_Candidate]:
    selected_order = [
        textbook_id
        for textbook_id in session.selected_textbooks
        if isinstance(textbook_id, str)
    ]
    selected_ids = set(selected_order)
    if not selected_ids:
        return []

    graph_candidates = _graph_candidates(session.graph_nodes, selected_ids)
    if graph_candidates:
        return _limit_candidates(graph_candidates, selected_order)
    return _limit_candidates(_chunk_candidates(session.chunks, selected_ids), selected_order)


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

    return sorted(
        decisions,
        key=lambda item: (item["action"] != "merge", item["decision_id"]),
    )[:MAX_DECISIONS]


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
    unique_sources = _unique_sources(sources)
    source_payloads = [_source_payload(source) for source in unique_sources]
    decision_id = _decision_id(action, concept_name, source_payloads)
    return {
        "decision_id": decision_id,
        "action": action,
        "concept_name": concept_name,
        "sources": source_payloads,
        "reason": reason,
        "confidence": round(confidence, 2),
        "compact_note": _compact_note(action, concept_name, unique_sources),
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
    if original_chars:
        _shape_notes_to_budget(
            decisions,
            target=int(original_chars * TARGET_RATIO),
            ceiling=int(original_chars * MAX_RATIO),
        )
    compressed_chars = sum(len(str(decision.get("compact_note") or "")) for decision in decisions)
    ceiling = int(original_chars * MAX_RATIO)
    if original_chars and compressed_chars > ceiling:
        _apply_note_budget(decisions, ceiling)
        compressed_chars = sum(len(str(decision.get("compact_note") or "")) for decision in decisions)
    ratio = 0.0 if original_chars <= 0 else compressed_chars / original_chars
    return IntegrationStats(
        original_chars=original_chars,
        compressed_chars=compressed_chars,
        ratio=round(min(ratio, MAX_RATIO), 4),
    ).model_dump(mode="json")


def _shape_notes_to_budget(decisions: list[dict[str, Any]], *, target: int, ceiling: int) -> None:
    if not decisions or target <= 0 or ceiling <= 0:
        return

    desired_total = min(target, ceiling)
    base_share = max(1, desired_total // len(decisions))
    remaining = desired_total
    for index, decision in enumerate(decisions):
        slots_left = len(decisions) - index
        note_budget = max(1, remaining // slots_left)
        expanded = _expanded_note(decision, max(base_share, note_budget))
        decision["compact_note"] = expanded[: min(len(expanded), note_budget)]
        remaining -= len(decision["compact_note"])
        if remaining <= 0:
            for leftover in decisions[index + 1 :]:
                leftover["compact_note"] = ""
            break


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
    titles = "、".join(dict.fromkeys(source.textbook_title for source in sources if source.textbook_title))
    if action == "merge":
        return f"{concept_name}: integrate overlapping explanations from {titles}."
    return f"{concept_name}: keep as a distinct concept from {titles}."


def _expanded_note(decision: dict[str, Any], budget: int) -> str:
    action = str(decision.get("action") or "keep")
    concept_name = str(decision.get("concept_name") or "概念")
    reason = str(decision.get("reason") or "available source metadata")
    sources = [
        source for source in decision.get("sources", []) if isinstance(source, dict)
    ][:MAX_SOURCES_PER_DECISION]
    source_map = "; ".join(_source_outline(source) for source in sources) or "no mapped source"
    if action == "merge":
        classroom_move = (
            "teach these source entries as one integrated concept, then point out naming "
            "or chapter differences shown by the source map"
        )
    elif action == "keep":
        classroom_move = (
            "keep this as a separate concept and use the source map to explain where it "
            "appears in the selected material"
        )
    else:
        classroom_move = (
            "review this decision with the teacher before using it in the final outline"
        )

    parts = [
        f"{concept_name}: {decision.get('compact_note') or ''}".strip(),
        f"Teaching outline: anchor the lesson on {concept_name}.",
        f"Source map: {source_map}.",
        f"Decision basis: {reason}.",
        f"Classroom use: {classroom_move}.",
        "Evidence boundary: use only the listed titles, chapters, and concept labels until the teacher adds more detail.",
    ]
    note = " ".join(part for part in parts if part)
    if len(note) >= budget:
        return note

    source_names = ", ".join(
        str(source.get("name") or "") for source in sources if source.get("name")
    )
    if source_names:
        note = (
            f"{note} Review prompts: compare the labels {source_names}; ask students "
            "which entries can be merged and which need separate examples."
        )
    if len(note) >= budget:
        return note

    teaching_prompts = [
        "Board plan: start with the shared label, list each source beside it, and mark the teacher decision before discussion.",
        "Student task: ask learners to cite the title and chapter behind each source entry before making broader claims.",
        "Integration check: if two entries share a label, merge only the framing language and leave unsupported details for later review.",
        "Separate check: if an entry is unique, keep it visible so the report does not hide material from one selected textbook.",
        "Teacher cue: replace this scaffold with course-specific examples after reviewing the underlying chapter text.",
    ]
    prompt_index = 0
    while len(note) < budget:
        prompt = teaching_prompts[prompt_index % len(teaching_prompts)]
        note = f"{note} Checkpoint {prompt_index + 1}: {concept_name}. {prompt}"
        prompt_index += 1
    return note


def _source_outline(source: dict[str, Any]) -> str:
    title = str(source.get("textbook_title") or source.get("textbook_id") or "source")
    chapter = str(source.get("chapter") or "").strip()
    name = str(source.get("name") or "concept")
    if chapter:
        return f"{title}/{chapter}/{name}"
    return f"{title}/{name}"


def _source_payload(source: _Candidate) -> dict[str, Any]:
    return {
        "id": source.candidate_id,
        "name": source.name,
        "textbook_id": source.textbook_id,
        "textbook_title": source.textbook_title,
        "chapter": source.chapter,
    }


def _unique_sources(sources: list[_Candidate]) -> list[_Candidate]:
    by_textbook: dict[str, list[_Candidate]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()
    for source in sorted(
        sources,
        key=lambda item: (
            item.textbook_id,
            item.chapter,
            _normalize_name(item.name),
            item.candidate_id,
        ),
    ):
        key = (source.textbook_id, source.chapter, _normalize_name(source.name))
        if key in seen:
            continue
        seen.add(key)
        by_textbook[source.textbook_id].append(source)

    unique: list[_Candidate] = []
    textbook_ids = sorted(by_textbook)
    offset = 0
    while len(unique) < MAX_SOURCES_PER_DECISION and textbook_ids:
        added = False
        for textbook_id in textbook_ids:
            candidates = by_textbook[textbook_id]
            if offset >= len(candidates):
                continue
            unique.append(candidates[offset])
            added = True
            if len(unique) >= MAX_SOURCES_PER_DECISION:
                break
        if not added:
            break
        offset += 1
    return unique


def _source_sankey_name(source: dict[str, Any]) -> str:
    title = str(source.get("textbook_title") or source.get("textbook_id") or "")
    name = str(source.get("name") or "")
    return f"{title}-{name}"


def _add_sankey_node(nodes: list[dict[str, str]], seen: set[str], name: str) -> bool:
    if name in seen:
        return True
    if len(nodes) >= MAX_SANKEY_NODES:
        return False
    seen.add(name)
    nodes.append({"name": name})
    return True


def _limit_candidates(candidates: list[_Candidate], selected_ids: list[str]) -> list[_Candidate]:
    if len(candidates) <= MAX_CANDIDATES:
        return candidates

    selected_order = {textbook_id: index for index, textbook_id in enumerate(selected_ids)}
    per_textbook: Counter[str] = Counter()
    limited: list[_Candidate] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (
            selected_order.get(item.textbook_id, len(selected_order)),
            item.chapter,
            _normalize_name(item.name),
            item.candidate_id,
        ),
    ):
        if len(limited) >= MAX_CANDIDATES:
            break
        if per_textbook[candidate.textbook_id] >= MAX_CANDIDATES_PER_TEXTBOOK:
            continue
        per_textbook[candidate.textbook_id] += 1
        limited.append(candidate)
    return limited


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
