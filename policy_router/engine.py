import json
from jinja2 import Environment, Undefined

from policy_router.models import PolicyProxyRule

# --- Safe Jinja environment (prevents undefined errors) ---
class SafeUndefined(Undefined):
    def _fail_with_undefined_error(self, *args, **kwargs):
        return ""

env = Environment(undefined=SafeUndefined)


def _render_jinja(value, context):
    """
    Render a single string using Jinja2.
    Returns the original value if it's not a string or fails.
    """
    if not isinstance(value, str):
        return value
    try:
        return env.from_string(value).render(**context)
    except Exception:
        return value


def _apply_jinja_to_structure(data, context):
    """
    Recursively walk dicts/lists and apply jinja rendering to all strings.
    """
    if isinstance(data, dict):
        return {k: _apply_jinja_to_structure(v, context) for k, v in data.items()}
    if isinstance(data, list):
        return [_apply_jinja_to_structure(x, context) for x in data]
    return _render_jinja(data, context)


def evaluate_policy(rule: PolicyProxyRule, call_info: dict):
    """
    Main entry point:
    Given a rule + call_info → returns the final response dict (Jinja rendered).
    """
    response = rule.response or {}

    # Apply jinja rendering to every string in the response structure
    rendered = _apply_jinja_to_structure(response, call_info)

    return rendered
