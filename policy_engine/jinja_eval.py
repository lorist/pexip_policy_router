from jinja2 import Environment, Undefined

class SafeUndefined(Undefined):
    def _fail_with_undefined_error(self, *args, **kwargs):
        return ""

env = Environment(undefined=SafeUndefined)

def render_jinja_template(value: str, context: dict):
    if not isinstance(value, str):
        return value
    try:
        template = env.from_string(value)
        return template.render(**context)
    except Exception:
        return value  # fail safe
