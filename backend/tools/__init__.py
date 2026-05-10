from collections.abc import Mapping
from typing import Any


def get_item_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def set_item_value(item: Any, key: str, value: Any) -> None:
    if isinstance(item, dict):
        item[key] = value
        return
    setattr(item, key, value)


def to_plain_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    if hasattr(item, "__dict__"):
        return dict(vars(item))
    return {"value": item}


def session_value(session: Any, key: str, default: Any = None) -> Any:
    return get_item_value(session, key, default)
