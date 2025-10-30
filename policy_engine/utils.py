import re
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("policy_engine.utils")

# regex for incoming call_info so we can use values in responses
_variable_re = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")

def evaluate_single_condition(field_value: Any, operator: str, expected_value: str) -> bool:
    """Evaluate a single atomic condition."""
    try:
        # Normalize types for comparison
        if isinstance(field_value, str):
            fv = field_value.lower()
            ev = str(expected_value).lower()
        else:
            fv = field_value
            ev = expected_value

        # String-based matching
        if operator == "equals":
            return fv == ev
        elif operator == "not_equals":
            return fv != ev
        elif operator == "contains":
            return ev in fv if isinstance(fv, str) else False
        elif operator == "starts_with":
            return fv.startswith(ev)
        elif operator == "ends_with":
            return fv.endswith(ev)
        elif operator == "regex_match":
            return bool(re.search(ev, str(fv)))
        elif operator in (">", "greater_than"):
            return float(fv) > float(ev)
        elif operator in ("<", "less_than"):
            return float(fv) < float(ev)
        elif operator in (">=", "greater_or_equal"):
            return float(fv) >= float(ev)
        elif operator in ("<=", "less_or_equal"):
            return float(fv) <= float(ev)
        elif operator == "in_list":
            return fv in [x.strip() for x in ev.split(",")]
        elif operator == "not_in_list":
            return fv not in [x.strip() for x in ev.split(",")]
        elif operator == "is_true":
            return bool(fv) is True
        elif operator == "is_false":
            return bool(fv) is False
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False
    except Exception as e:
        logger.exception(f"Error evaluating condition ({field_value}, {operator}, {expected_value}): {e}")
        return False


def evaluate_conditions_group(group: Dict, call_info: Dict[str, Any], path="root") -> Tuple[bool, List[str]]:
    """
    Recursively evaluate a nested condition group.
    Returns (matched, failed_conditions)
    """
    combiner = group.get("combiner", "all")
    rules = group.get("rules", [])
    failed = []

    results = []

    for i, rule in enumerate(rules):
        if "rules" in rule:  # nested group
            matched, subfailed = evaluate_conditions_group(rule, call_info, f"{path}.{i}")
            results.append(matched)
            failed.extend(subfailed)
        else:
            field = rule.get("field")
            operator = rule.get("operator", "equals")
            expected = rule.get("value", "")
            actual = call_info.get(field)
            matched = evaluate_single_condition(actual, operator, expected)
            results.append(matched)
            if not matched:
                failed.append(f"{path}.{field}: expected {expected!r}, got {actual!r}")

    if combiner == "all":
        group_match = all(results)
    elif combiner == "any":
        group_match = any(results)
    else:
        group_match = False
        logger.warning(f"Invalid combiner: {combiner}")

    return group_match, failed


def evaluate_conditions(conditions: Dict, call_info: Dict[str, Any]) -> Dict:
    """
    Top-level evaluator that matches call_info against nested conditions.
    Returns dict with match status and failure details.
    """
    try:
        matched, failed = evaluate_conditions_group(conditions, call_info)
        return {
            "matched": matched,
            "failed_conditions": failed,
        }
    except Exception as e:
        logger.exception(f"Error evaluating conditions: {e}")
        return {"matched": False, "failed_conditions": [str(e)]}

def apply_template(data, context):
    """
    Recursively replace {{key}} placeholders in dict/string values using context.
    """
    if isinstance(data, dict):
        return {k: apply_template(v, context) for k, v in data.items()}
    if isinstance(data, list):
        return [apply_template(i, context) for i in data]
    if isinstance(data, str):
        for key, val in context.items():
            data = data.replace(f"{{{{ {key} }}}}", str(val))
            data = data.replace(f"{{{{{key}}}}}", str(val))
        return data
    return data

def normalize_policy_response(data):
    """
    Ensure the returned policy response matches Pexip expected structure.
    """
    if data is None:
        return {"status": "success", "action": "continue"}

    # If already normalized, leave it alone
    if isinstance(data, dict) and data.get("status") and data.get("action"):
        return data

    # Otherwise wrap as result
    return {
        "status": "success",
        "action": "continue",
        "result": data
    }
