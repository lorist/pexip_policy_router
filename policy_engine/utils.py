import re
from typing import Any, Dict, List


def _get_by_path(data: Dict[str, Any], path: str, default=None):
    """
    Resolve dotted paths like "participant.display_name" or "protocol".
    Supports list indices: "participants.0.alias"
    """
    cur = data
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                idx = int(part)
                cur = cur[idx]
            except (ValueError, IndexError):
                return default
        elif isinstance(cur, dict):
            if part in cur:
                cur = cur[part]
            else:
                return default
        else:
            return default
    return cur


def _compare(lhs, op: str, rhs):
    if op == "eq":
        return lhs == rhs
    if op == "ne":
        return lhs != rhs
    if op == "gt":
        try:
            return lhs > rhs
        except Exception:
            return False
    if op == "gte":
        try:
            return lhs >= rhs
        except Exception:
            return False
    if op == "lt":
        try:
            return lhs < rhs
        except Exception:
            return False
    if op == "lte":
        try:
            return lhs <= rhs
        except Exception:
            return False
    if op == "in":
        try:
            return lhs in rhs
        except Exception:
            return False
    if op == "contains":
        try:
            return rhs in lhs
        except Exception:
            return False
    if op == "startswith":
        try:
            return str(lhs).startswith(str(rhs))
        except Exception:
            return False
    if op == "endswith":
        try:
            return str(lhs).endswith(str(rhs))
        except Exception:
            return False
    if op == "regex":
        try:
            return re.search(str(rhs), str(lhs)) is not None
        except Exception:
            return False
    return False


def evaluate_conditions(call_info: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
    """
    Evaluate a conditions JSON object against a call_info dict.

    Structure:
    {
      "combiner": "all"|"any",
      "rules": [
        {"path": "protocol", "op": "eq", "value": "webrtc"},
        ...
      ]
    }
    """
    if not conditions:
        # default: no conditions means "match all"
        return True

    rules: List[Dict[str, Any]] = conditions.get("rules", [])
    combiner: str = conditions.get("combiner", "all").lower()

    results = []
    for rule in rules:
        path = rule.get("path", "")
        op = rule.get("op", "eq")
        value = rule.get("value")
        lhs = _get_by_path(call_info, path)
        results.append(_compare(lhs, op, value))

    if combiner == "any":
        return any(results) if results else True
    # default to "all"
    return all(results) if results else True
