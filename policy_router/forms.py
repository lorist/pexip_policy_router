import json
from django import forms
from .models import PolicyProxyRule


class PolicyProxyRuleForm(forms.ModelForm):
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

            # Multi-select dropdowns for protocols + call directions
            "protocols": forms.SelectMultiple(
                choices=PolicyProxyRule.PROTOCOL_CHOICES,
                attrs={"class": "form-select", "id": "id_protocols"},
            ),
            "call_directions": forms.SelectMultiple(
                choices=PolicyProxyRule.CALL_DIRECTION_CHOICES,
                attrs={"class": "form-select", "id": "id_call_directions"},
            ),

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
        """Always return a list (never None)."""
        return self.cleaned_data.get("protocols") or []

    def clean_call_directions(self):
        """Always return a list (never None)."""
        return self.cleaned_data.get("call_directions") or []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Ensure defaults for overrides if toggles are set
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
