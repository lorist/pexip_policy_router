import json
from django import forms
from .models import PolicyProxyRule


class CSVImportForm(forms.Form):
    csv_file = forms.FileField(label="Select CSV file")


class PolicyProxyRuleForm(forms.ModelForm):
    protocols = forms.MultipleChoiceField(
        choices=PolicyProxyRule.PROTOCOL_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select"}),
        help_text="Leave empty to match any protocol."
    )

    call_directions = forms.MultipleChoiceField(
        choices=PolicyProxyRule.CALL_DIRECTION_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select"}),
        help_text="Leave empty to match any call direction."
    )

    class Meta:
        model = PolicyProxyRule
        fields = [
            "name",
            "regex",
            "priority",
            "is_active",
            "protocols",
            "call_directions",
            "service_target_url",
            "always_continue_service",
            "override_service_response",
            "participant_target_url",
            "always_continue_participant",
            "override_participant_response",
            "basic_auth_username",
            "basic_auth_password",
        ]
        labels = {
            "always_continue_service": "Custom response (Service)",
            "always_continue_participant": "Custom response (Participant)",
        }
        widgets = {
            "regex": forms.TextInput(attrs={"placeholder": r"^room\-\d+$"}),
            "service_target_url": forms.URLInput(attrs={"placeholder": "https://upstream.example.com"}),
            "participant_target_url": forms.URLInput(attrs={"placeholder": "https://upstream.example.com"}),
            "basic_auth_password": forms.PasswordInput(render_value=True),
            "override_service_response": forms.Textarea(
                attrs={"rows": 4, "placeholder": '{"status": "success", "action": "continue"}'}
            ),
            "override_participant_response": forms.Textarea(
                attrs={"rows": 4, "placeholder": '{"status": "success", "action": "continue"}'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["protocols"].required = False
        self.fields["call_directions"].required = False

        # Normalize JSONField values (None → [])
        self.initial["protocols"] = list(self.instance.protocols or [])
        self.initial["call_directions"] = list(self.instance.call_directions or [])

        # Default JSON responses for toggles
        if self.instance.always_continue_service and not self.instance.override_service_response:
            self.initial["override_service_response"] = '{"status": "success", "action": "continue"}'
        if self.instance.always_continue_participant and not self.instance.override_participant_response:
            self.initial["override_participant_response"] = '{"status": "success", "action": "continue"}'

    def full_clean(self):
        """Handle case where all items are deselected (no key in POST)."""
        data = self.data.copy()
        for field_name in ["protocols", "call_directions"]:
            if field_name not in data:
                data.setlist(field_name, [])
        self.data = data
        super().full_clean()

    def clean_protocols(self):
        return self.cleaned_data.get("protocols") or []

    def clean_call_directions(self):
        return self.cleaned_data.get("call_directions") or []

    def clean_override_service_response(self):
        data = self.cleaned_data.get("override_service_response")
        if data in (None, "", {}):
            return None
        try:
            return json.loads(data) if isinstance(data, str) else data
        except (ValueError, TypeError):
            raise forms.ValidationError("Invalid JSON for service override response.")

    def clean_override_participant_response(self):
        data = self.cleaned_data.get("override_participant_response")
        if data in (None, "", {}):
            return None
        try:
            return json.loads(data) if isinstance(data, str) else data
        except (ValueError, TypeError):
            raise forms.ValidationError("Invalid JSON for participant override response.")
