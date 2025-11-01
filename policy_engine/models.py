from django.db import models
from django.utils.translation import gettext_lazy as _
from policy_router.models import PolicyProxyRule

def default_conditions():
    # Root group always exists
    return {"combiner": "all", "rules": []}

def default_response():
    return {"action": "continue"}

class PolicyLogic(models.Model):
    class RuleType(models.TextChoices):
        PARTICIPANT = "participant", _("Participant")
        SERVICE = "service", _("Service")

    PARTICIPANT = RuleType.PARTICIPANT
    SERVICE = RuleType.SERVICE

    rule = models.ForeignKey(
        PolicyProxyRule,
        on_delete=models.CASCADE,
        related_name="advanced_logic",
    )

    ACTION_CHOICES = [
        ("allow", "Allow"),
        ("reject", "Reject"),
    ]

    action = models.CharField(
        max_length=10,
        choices=ACTION_CHOICES,
        default="allow"
    )

    reject_reason = models.CharField(
        max_length=200,
        blank=True,
        default=""
    )
    rule_type = models.CharField(max_length=20, choices=RuleType.choices)
    enabled = models.BooleanField(default=False)

    # ✅ Correct default shapes
    conditions = models.JSONField(default=default_conditions, blank=True)
    response = models.JSONField(default=default_response, blank=True)
    reject_reason = models.CharField(max_length=255, blank=True, default="")
    description = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        unique_together = (("rule", "rule_type"),)
        indexes = [models.Index(fields=["rule", "rule_type"])]

    def __str__(self):
        return f"{self.rule.name} [{self.rule_type}]"
