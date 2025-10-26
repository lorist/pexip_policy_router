import json
from django import forms
from .models import PolicyLogic


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
    # Store JSON as text in the form (with validation) for a nicer editing UX
    conditions_text = forms.CharField(
        required=False,
        widget=JSONTextarea(attrs={"placeholder": '{ "combiner": "all", "rules": [] }'}),
        help_text="JSON object describing rules. Leave blank for match-all.",
    )
    response_text = forms.CharField(
        required=False,
        widget=JSONTextarea(attrs={"placeholder": "{}"}),
        help_text="JSON object returned when conditions match.",
    )

    class Meta:
        model = PolicyLogic
        fields = ["enabled", "description"]

    def __init__(self, *args, **kwargs):
        instance: PolicyLogic = kwargs.get("instance")
        initial = kwargs.setdefault("initial", {})
        if instance:
            initial["conditions_text"] = json.dumps(instance.conditions or {}, indent=2)
            initial["response_text"] = json.dumps(instance.response or {}, indent=2)
        super().__init__(*args, **kwargs)

    def clean_conditions_text(self):
        raw = self.cleaned_data.get("conditions_text") or ""
        if raw.strip() == "":
            return {}  # treat empty as match-all
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise forms.ValidationError("Conditions must be a JSON object.")
            return data
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f"Invalid JSON: {e}")

    def clean_response_text(self):
        raw = self.cleaned_data.get("response_text") or "{}"
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise forms.ValidationError("Response must be a JSON object.")
            return data
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f"Invalid JSON: {e}")

    def save(self, commit=True):
        obj: PolicyLogic = super().save(commit=False)
        obj.conditions = self.cleaned_data["cleaned_conditions"] = self.cleaned_data[
            "conditions_text"
        ]
        obj.response = self.cleaned_data["cleaned_response"] = self.cleaned_data[
            "response_text"
        ]
        if commit:
            obj.save()
        return obj
