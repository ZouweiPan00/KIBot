from collections import Counter
from typing import Any

from backend.tools import get_item_value, session_value


COMPACT_TEXT_FIELDS = (
    "compact",
    "compact_note",
    "compact_summary",
    "summary",
    "result_summary",
)


def get_compression_stats(session: Any) -> dict[str, float | int]:
    textbooks = session_value(session, "textbooks", []) or []
    decisions = session_value(session, "integration_decisions", []) or []

    original_chars = sum(_safe_int(get_item_value(textbook, "total_chars", 0)) for textbook in textbooks)
    compressed_chars = sum(_decision_compact_chars(decision) for decision in decisions)
    compression_ratio = compressed_chars / original_chars if original_chars else 0

    return {
        "original_chars": original_chars,
        "compressed_chars": compressed_chars,
        "compression_ratio": compression_ratio,
    }


def get_token_usage(session: Any) -> dict[str, int]:
    usage = session_value(session, "token_usage", None)
    return {
        "calls": _safe_int(get_item_value(usage, "calls", 0)),
        "input_tokens": _safe_int(get_item_value(usage, "input_tokens", 0)),
        "output_tokens": _safe_int(get_item_value(usage, "output_tokens", 0)),
        "total_tokens": _safe_int(get_item_value(usage, "total_tokens", 0)),
    }


def get_graph_summary(session: Any) -> dict[str, Any]:
    nodes = session_value(session, "graph_nodes", []) or []
    edges = session_value(session, "graph_edges", []) or []
    categories: Counter[str] = Counter()
    textbooks: Counter[str] = Counter()

    for node in nodes:
        category = get_item_value(node, "category")
        textbook_id = get_item_value(node, "textbook_id")
        if category:
            categories[str(category)] += 1
        if textbook_id:
            textbooks[str(textbook_id)] += 1

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "categories": dict(categories),
        "textbooks": dict(textbooks),
    }


def _decision_compact_chars(decision: Any) -> int:
    for field in COMPACT_TEXT_FIELDS:
        value = get_item_value(decision, field)
        if isinstance(value, str) and value:
            return len(value)
    return 0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
