# policy_proxy/forms.py
from django import forms
from .models import PolicyProxyRule

class PolicyProxyRuleForm(forms.ModelForm):
    use_advanced_logic = forms.BooleanField(required=False, label="Enable advanced logic")

    class Meta:
        model = PolicyProxyRule
        fields = ['name', 'source', 'destination', 'use_advanced_logic']
