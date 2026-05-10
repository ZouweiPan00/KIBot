from typing import Any

from backend.schemas.session import KIBotSession
from backend.tools import get_item_value
from backend.tools.stats_tool import (
    get_compression_stats,
    get_graph_summary,
    get_token_usage,
)


REQUIRED_SECTIONS = (
    "整合概览",
    "整合决策摘要",
    "知识图谱统计",
    "重点整合案例",
    "教学完整性说明",
    "局限与改进",
)


def generate_report_markdown(session: KIBotSession) -> str:
    selected_count = len(session.selected_textbooks or [])
    decisions = session.integration_decisions or []
    graph_summary = get_graph_summary(session)
    token_usage = get_token_usage(session)
    compression_ratio = _compression_ratio(session)

    lines = [
        "# KIBot 教材整合报告",
        "",
        "## 整合概览",
        f"- 会话 ID：{session.session_id}",
        f"- 已选择教材：{selected_count} 本",
        f"- 整合决策：{len(decisions)} 条",
        f"- 压缩比例：{_format_percent(compression_ratio)}",
        f"- Token 使用：{token_usage['total_tokens']}",
        "",
        "## 整合决策摘要",
    ]
    lines.extend(_decision_summary_lines(decisions))
    lines.extend(
        [
            "",
            "## 知识图谱统计",
            f"- 知识图谱节点：{graph_summary['node_count']} 个",
            f"- 知识图谱边：{graph_summary['edge_count']} 条",
        ]
    )
    lines.extend(_graph_detail_lines(graph_summary))
    lines.extend(
        [
            "",
            "## 重点整合案例",
        ]
    )
    lines.extend(_case_lines(decisions))
    lines.extend(
        [
            "",
            "## 教学完整性说明",
            _teaching_integrity_note(selected_count, decisions, graph_summary),
            "",
            "## 局限与改进",
            "- 报告基于当前会话数据生成，未调用外部模型或人工补充材料。",
            "- 若教材、知识图谱或整合决策为空，建议先完成上传、构图与整合确认流程。",
            "- 后续可补充章节覆盖率、教师审核意见和学习目标映射，以提升报告解释力。",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def _decision_summary_lines(decisions: list[Any]) -> list[str]:
    if not decisions:
        return ["- 暂无整合决策。"]

    action_counts: dict[str, int] = {}
    for decision in decisions:
        action = str(get_item_value(decision, "action", "未标注") or "未标注")
        action_counts[action] = action_counts.get(action, 0) + 1

    lines = [f"- 决策总数：{len(decisions)} 条"]
    for action in sorted(action_counts):
        lines.append(f"- {action}：{action_counts[action]} 条")
    return lines


def _graph_detail_lines(graph_summary: dict[str, Any]) -> list[str]:
    if graph_summary["node_count"] == 0:
        return ["- 暂无知识图谱节点。"]

    lines: list[str] = []
    categories = graph_summary.get("categories") or {}
    if categories:
        category_text = "，".join(
            f"{category} {count}" for category, count in sorted(categories.items())
        )
        lines.append(f"- 节点类别：{category_text}")
    return lines


def _case_lines(decisions: list[Any]) -> list[str]:
    if not decisions:
        return ["- 暂无重点整合案例。"]

    lines: list[str] = []
    for decision in decisions[:3]:
        decision_id = get_item_value(decision, "decision_id", "未编号")
        action = get_item_value(decision, "action", "未标注")
        summary = _first_text(
            decision,
            ("summary", "result_summary", "compact", "compact_summary", "reason"),
            "暂无案例说明",
        )
        reason = _first_text(decision, ("reason", "teacher_note"), "")
        line = f"- {decision_id}（{action}）：{summary}"
        if reason and reason != summary:
            line = f"{line}；依据：{reason}"
        lines.append(line)
    return lines


def _teaching_integrity_note(
    selected_count: int,
    decisions: list[Any],
    graph_summary: dict[str, Any],
) -> str:
    if selected_count == 0 and not decisions and graph_summary["node_count"] == 0:
        return "当前会话尚未形成完整整合链路，报告保留空状态说明，便于后续补充教材、图谱与决策。"

    return (
        "当前报告从已选教材、整合决策与知识图谱三类会话数据交叉说明教学内容，"
        "用于帮助教师检查核心概念、案例取舍与知识连接是否保持完整。"
    )


def _compression_ratio(session: KIBotSession) -> float:
    for decision in session.integration_decisions or []:
        value = _numeric_value(
            decision,
            ("compression_ratio", "compression", "ratio"),
        )
        if value is not None:
            return value

    stats = get_compression_stats(session)
    return float(stats["compression_ratio"])


def _numeric_value(item: Any, fields: tuple[str, ...]) -> float | None:
    for field in fields:
        value = get_item_value(item, field)
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_text(item: Any, fields: tuple[str, ...], default: str) -> str:
    for field in fields:
        value = get_item_value(item, field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"
