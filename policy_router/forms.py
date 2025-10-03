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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pre-populate defaults if checkboxes are ticked but no text provided
        if self.instance.always_continue_service and not self.instance.override_service_response:
            self.initial["override_service_response"] = '{"status": "success", "action": "continue"}'
        if self.instance.always_continue_participant and not self.instance.override_participant_response:
            self.initial["override_participant_response"] = '{"status": "success", "action": "continue"}'
