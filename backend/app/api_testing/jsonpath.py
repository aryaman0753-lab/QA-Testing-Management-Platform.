import re
from typing import Any

_TOKEN = re.compile(r"(?:\.([A-Za-z_][A-Za-z0-9_-]*))|(?:\[(\d+)\])")
MISSING = object()


def json_path_get(document: Any, path: str) -> Any:
    """Small, deterministic JSONPath subset: $.object.key[0].value."""
    if path == "$":
        return document
    if not path.startswith("$"):
        raise ValueError("JSON path must start with '$'.")
    current = document
    position = 1
    while position < len(path):
        match = _TOKEN.match(path, position)
        if not match:
            raise ValueError("Unsupported JSON path syntax.")
        key, index = match.groups()
        if key is not None:
            if not isinstance(current, dict) or key not in current:
                return MISSING
            current = current[key]
        else:
            if not isinstance(current, list) or int(index) >= len(current):
                return MISSING
            current = current[int(index)]
        position = match.end()
    return current
