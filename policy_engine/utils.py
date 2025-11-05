import re
import logging
from typing import Any, Dict, List, Tuple
from jinja2 import Environment, StrictUndefined

logger = logging.getLogger("policy_engine.utils")

# regex for incoming call_info so we can use values in responses
_variable_re = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")

def get_nested(data, dotted):
    """
    Resolve dotted keys like 'idp_attributes.mail' into nested dictionaries.
    Returns None if any part is missing.
    """
    if not isinstance(data, dict):
        return None

    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def evaluate_single_condition(field_value: Any, operator: str, expected_value: str, call_info=None) -> bool:
    """
    Evaluate a single condition, supporting Jinja templating and extended template operators.
    """
    # ---- Template-based comparison ----
    if operator.startswith("template_"):
        try:
            # Render both sides via Jinja (allows full logic on expected_value)
            left = apply_template(str(field_value), call_info or {})
            right = apply_template(str(expected_value), call_info or {})
        except Exception:
            return False

        # Normalize to strings
        left = "" if left is None else str(left)
        right = "" if right is None else str(right)

        if operator == "template_equals":
            return left == right

        elif operator == "template_contains":
            return right in left

        elif operator == "template_starts_with":
            return left.startswith(right)

        elif operator == "template_regex_match":
            try:
                return bool(re.search(right, left))
            except re.error:
                return False

        elif operator == "template_boolean":
            # The rendered expression must equal literal "true" (case-insensitive)
            return right.strip().lower() == "true"

        else:
            logger.warning(f"Unknown template operator: {operator}")
            return False

    # ---- Standard operators ----
    try:
        if isinstance(field_value, str):
            fv = field_value.lower()
            ev = str(expected_value).lower()
        else:
            fv = field_value
            ev = expected_value

        if operator == "equals":
            return fv == ev
        elif operator == "not_equals":
            return fv != ev
        elif operator == "contains":
            return isinstance(fv, str) and ev in fv
        elif operator == "starts_with":
            return isinstance(fv, str) and fv.startswith(ev)
        elif operator == "ends_with":
            return isinstance(fv, str) and fv.endswith(ev)
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

            # ✅ NEW: dotted lookup support
            actual = get_nested(call_info, field)

            matched = evaluate_single_condition(actual, operator, expected, call_info)

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

def explain_condition(field, operator, expected, call_info):
    """
    Returns a dict describing how a condition was evaluated.
    """
    from jinja2 import Template

    actual = get_nested(call_info, field)

    expected_raw = expected
    expected_rendered = expected

    if operator.startswith("template_"):
        try:
            expected_rendered = Template(expected).render(**call_info)
        except Exception:
            pass

    result = evaluate_single_condition(actual, operator, expected_raw, call_info)

    return {
        "field": field,
        "operator": operator,
        "expected_raw": expected_raw,
        "expected_rendered": expected_rendered,
        "actual": actual,
        "result": result,
    }



from jinja2 import Environment, StrictUndefined

jinja_env = Environment(
    autoescape=False,
    undefined=StrictUndefined,  # Throw error if missing variable → safer debugging
    trim_blocks=True,
    lstrip_blocks=True,
)

def apply_template(data, context):
    """
    Recursively apply Jinja2 rendering to all strings in a dict/list.
    Allows expressions like {{ var|upper }} and {% if %} blocks.
    """
    if isinstance(data, dict):
        return {k: apply_template(v, context) for k, v in data.items()}

    if isinstance(data, list):
        return [apply_template(v, context) for v in data]

    if isinstance(data, str):
        try:
            template = jinja_env.from_string(data)
            return template.render(**context)
        except Exception:
            # If template parsing fails, return raw string for safety
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

