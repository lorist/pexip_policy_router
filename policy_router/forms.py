from django import forms
from .models import PolicyProxyRule

class PolicyProxyRuleForm(forms.ModelForm):
    class Meta:
        model = PolicyProxyRule
        fields = [
            "name",
            "regex",
            "service_target_url",
            "participant_target_url",
            "is_active",
            "priority",
            "basic_auth_username",
            "basic_auth_password",
        ]
        labels = {
            "regex": "Local Alias Regex",
        }
        widgets = {
            "regex": forms.TextInput(attrs={"placeholder": r"^room\-\d+$"}),
            "service_target_url": forms.URLInput(attrs={"placeholder": "https://upstream.example.com"}),
            "participant_target_url": forms.URLInput(attrs={"placeholder": "https://upstream.example.com"}),
            "basic_auth_password": forms.PasswordInput(render_value=True),
        }
