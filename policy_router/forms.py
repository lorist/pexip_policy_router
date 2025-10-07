import json
from django import forms
from .models import PolicyProxyRule


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

    def clean_protocols(self):
        """Ensure a list is always stored, not JSON string."""
        return self.cleaned_data.get("protocols", [])

    def clean_call_directions(self):
        """Ensure a list is always stored, not JSON string."""
        return self.cleaned_data.get("call_directions", [])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set initial values from the instance (JSONField stores list)
        if isinstance(self.instance.protocols, list):
            self.initial["protocols"] = self.instance.protocols
        if isinstance(self.instance.call_directions, list):
            self.initial["call_directions"] = self.instance.call_directions

        # Default JSON responses if toggles are active but empty
        if self.instance.always_continue_service and not self.instance.override_service_response:
            self.initial["override_service_response"] = '{"status": "success", "action": "continue"}'
        if self.instance.always_continue_participant and not self.instance.override_participant_response:
            self.initial["override_participant_response"] = '{"status": "success", "action": "continue"}'

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
