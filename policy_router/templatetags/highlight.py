from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()

@register.filter
def highlight(text, search):
    if not search:
        return text
    try:
        pattern = re.compile(re.escape(search), re.IGNORECASE)
        highlighted = pattern.sub(
            lambda m: f'<mark style="background-color: yellow;">{m.group(0)}</mark>',
            str(text)
        )
        return mark_safe(highlighted)  # ✅ prevent auto-escaping
    except Exception:
        return text
