from django.db import models
from django.core.validators import MinLengthValidator
from django.utils.translation import gettext_lazy as _

# IMPORTANT: assumes you have PolicyProxyRule in policy_router.models
from policy_router.models import PolicyProxyRule


class PolicyLogic(models.Model):
    class RuleType(models.TextChoices):
        PARTICIPANT = "participant", _("Participant")
        SERVICE = "service", _("Service")

    rule = models.ForeignKey(
        PolicyProxyRule,
        on_delete=models.CASCADE,
        related_name="advanced_logics",
    )
    rule_type = models.CharField(max_length=20, choices=RuleType.choices)
    enabled = models.BooleanField(default=False)

    # Conditions: a JSON structure describing path/op/value conditions on call_info
    # Example:
    # {
    #   "combiner": "all",               # "all" (AND) | "any" (OR)
    #   "rules": [
    #     {"path": "call_direction", "op": "eq", "value": "in"},
    #     {"path": "protocol", "op": "in", "value": ["webrtc", "teams"]},
    #     {"path": "vendor", "op": "regex", "value": "pexip|cisco"},
    #   ]
    # }
    conditions = models.JSONField(default=dict, blank=True)

    # Response JSON returned if conditions evaluate to True
    # (Infinity-ready shape for participant/service policy)
    response = models.JSONField(default=dict, blank=True)

    # Optional description to help admins
    description = models.CharField(
        max_length=255, blank=True, default="", validators=[MinLengthValidator(0)]
    )

    class Meta:
        unique_together = [("rule", "rule_type")]
        indexes = [
            models.Index(fields=["rule", "rule_type"]),
        ]

    def __str__(self):
        return f"{self.rule} · {self.rule_type} · enabled={self.enabled}"
