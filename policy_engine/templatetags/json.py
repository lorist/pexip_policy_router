from django import template
import json

register = template.Library()

@register.filter
def dumps(value):
    return json.dumps(value)