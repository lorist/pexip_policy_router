import json
from django import forms
from .models import PolicyLogic
from .schema import SCHEMAS_BY_TYPE

class JSONTextarea(forms.Textarea):
    def __init__(self, **kwargs):
        attrs = kwargs.pop("attrs", {})
        default = {
            "rows": 10,
            "class": "form-control font-monospace",
            "spellcheck": "false",
        }
        default.update(attrs)
        super().__init__(attrs=default)


class PolicyLogicForm(forms.ModelForm):
    rule_type = forms.ChoiceField(
        choices=[("participant", "Participant Policy"), ("service", "Service Policy")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    field_name = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Select a call_info parameter to use in your condition",
    )

    operator = forms.ChoiceField(
        required=False,
        choices=[
            ("equals", "Equals"),
            ("not_equals", "Not Equals"),
            ("contains", "Contains"),
            ("starts_with", "Starts With"),
            ("gt", "Greater Than"),
            ("lt", "Less Than"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    value = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Value to compare against (type-sensitive)",
    )

    class Meta:
        model = PolicyLogic
        fields = ["enabled", "description"]

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        super().__init__(*args, **kwargs)

        schema = SCHEMAS_BY_TYPE.get(
            instance.rule_type if instance else "participant",
            {},
        )

        # Populate dropdown dynamically
        self.fields["field_name"].choices = [
            (k, f"{k} ({v['type']})") for k, v in schema.items()
        ]