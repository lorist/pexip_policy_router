import json
from django import forms
from .models import PolicyLogic


class JSONHiddenField(forms.CharField):
    """A hidden field for storing JSON data (from JS builder)."""
    widget = forms.HiddenInput()

    def clean(self, value):
        if not value:
            return {}
        try:
            data = json.loads(value)
            if not isinstance(data, dict):
                raise forms.ValidationError("Invalid JSON structure.")
            return data
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format.")


class PolicyLogicForm(forms.ModelForm):
    conditions = JSONHiddenField(required=False)
    response_action = forms.ChoiceField(
        required=False,
        choices=[("continue", "Continue"), ("reject", "Reject"), ("override", "Override")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    response_reason = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Optional reason or metadata.",
    )

    class Meta:
        model = PolicyLogic
        fields = ["enabled", "description", "conditions"]

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.conditions = self.cleaned_data["conditions"] or {"combiner": "all", "rules": []}
        obj.response = {
            "action": self.cleaned_data.get("response_action"),
            "reason": self.cleaned_data.get("response_reason"),
        }
        if commit:
            obj.save()
        return obj
