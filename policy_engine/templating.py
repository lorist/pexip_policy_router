import re

TEMPLATE_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")

def apply_template(value, call_info):
    """
    Replace {{ key }} placeholders in strings with values from call_info dict.
    Non-strings are returned unchanged.
    """
    if not isinstance(value, str):
        return value

    def replacer(match):
        key = match.group(1)
        return str(call_info.get(key, ""))

    return TEMPLATE_PATTERN.sub(replacer, value)


def resolve_response_templates(response_json, call_info):
    """
    Recursively walk response JSON and apply placeholder substitution.
    """
    if isinstance(response_json, dict):
        return {k: resolve_response_templates(v, call_info) for k, v in response_json.items()}

    if isinstance(response_json, list):
        return [resolve_response_templates(v, call_info) for v in response_json]

    return apply_template(response_json, call_info)
