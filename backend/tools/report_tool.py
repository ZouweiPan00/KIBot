from typing import Any

from backend.tools import get_item_value, session_value


def get_report(session: Any) -> dict[str, Any]:
    report = session_value(session, "report", None)
    return {
        "markdown": get_item_value(report, "markdown", ""),
        "updated_at": get_item_value(report, "updated_at"),
    }
