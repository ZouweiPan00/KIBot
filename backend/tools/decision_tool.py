from typing import Any

from backend.tools import get_item_value, session_value, set_item_value, to_plain_dict


def get_integration_decisions(session: Any) -> list[dict[str, Any]]:
    decisions = session_value(session, "integration_decisions", []) or []
    return [to_plain_dict(decision) for decision in decisions]


def update_decision(
    session: Any,
    decision_id: str,
    action: str,
    teacher_note: str,
) -> Any:
    decisions = session_value(session, "integration_decisions", []) or []
    for decision in decisions:
        if get_item_value(decision, "decision_id") == decision_id:
            set_item_value(decision, "action", action)
            set_item_value(decision, "teacher_note", teacher_note)
            set_item_value(decision, "status", "teacher_updated")
            return decision
    raise ValueError(f"Decision not found: {decision_id}")
