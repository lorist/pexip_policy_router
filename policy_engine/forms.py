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
    # JSON for conditions (hidden)
    conditions = forms.CharField(required=False, widget=forms.HiddenInput)

    # Only shown when Action = Reject
    reject_reason = forms.CharField(
        required=False,
        label="Reject Reason (displayed to caller)",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. Not allowed"
        })
    )
    service_new_alias = forms.CharField(
        required=False,
        label="Redirect to Alias",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "sip:someone@example.com"})
    )

    class Meta:
        model = PolicyLogic
        fields = [
            "enabled",
            "description",
            "conditions",
            "reject_reason",
        ]
        widgets = {
            "description": forms.Textarea(attrs={
                "rows": 2,
                "class": "form-control form-control-sm",
                "placeholder": "Optional description of this logic block"
            }),
        }

    def save(self, commit=True):
        """
        The view handles response building based on allow/reject mode.
        Here we ONLY store enabled, description, conditions, reject_reason.
        """
        obj = super().save(commit=False)

        # Ensure empty or missing conditions default cleanly
        obj.conditions = self.cleaned_data.get("conditions") or {
            "combiner": "all",
            "rules": []
        }

        # DO NOT touch obj.response here — handled in logic_editor view
        if commit:
            obj.save()

        return obj

