import json
from django import forms
from .models import PolicyLogic, IdentityAttribute


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


class IdentityAttributeForm(forms.ModelForm):
    class Meta:
        model = IdentityAttribute
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., title"}),
            "description": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional description"}),
        }


class PolicyLogicForm(forms.ModelForm):
    reject_reason = forms.CharField(
        required=False,
        label="Reject Reason",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Caller not allowed"}),
    )

    # Only used for service logic when redirect is chosen
    service_new_alias = forms.CharField(
        required=False,
        label="Redirect To Alias",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "sip:new_alias@example.com"}),
    )

    class Meta:
        model = PolicyLogic
        fields = [
            "enabled",
            "description",
            "reject_reason",
            "service_new_alias",
        ]
        widgets = {
            "enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        # Ensure redirect alias only required if redirect chosen
        # But action is handled by the view — we just avoid storing unrelated junk
        return cleaned

