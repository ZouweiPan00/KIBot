from typing import Any

from backend.tools import get_item_value, session_value, to_plain_dict


def get_selected_textbooks(session: Any) -> list[dict[str, Any]]:
    selected_items = session_value(session, "selected_textbooks", []) or []
    textbooks = session_value(session, "textbooks", []) or []
    textbooks_by_id = {}
    for textbook in textbooks:
        textbook_id = get_item_value(textbook, "textbook_id")
        legacy_id = get_item_value(textbook, "id")
        if textbook_id is not None:
            textbooks_by_id[textbook_id] = textbook
        if legacy_id is not None:
            textbooks_by_id[legacy_id] = textbook

    selected: list[dict[str, Any]] = []
    for item in selected_items:
        if isinstance(item, str) and item in textbooks_by_id:
            selected.append(to_plain_dict(textbooks_by_id[item]))
        else:
            selected.append(to_plain_dict(item))
    return selected
