from django.db import models
from django.utils.translation import gettext_lazy as _
from policy_router.models import PolicyProxyRule

def default_conditions():
    return {"combiner": "all", "rules": []}

def default_response():
    return {"status": "success", "action": "continue", "result": {}}

class IdentityAttribute(models.Model):
    """
    Defines IdP attributes (idp_attribute_*) that should appear in the
    advanced logic UI, condition builder, and Jinja suggestions.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Just the attribute name, e.g. 'title', 'mail', 'department'"
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional description shown in UI dropdowns and help tooltips."
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

# policy_engine/models.py

class IdentityValue(models.Model):
    """
    Stores per-user identity attributes collected from participant calls.
    Subject is a stable unique identity key (idp_uuid preferred).
    """
    subject = models.CharField(max_length=255, db_index=True)
    attrs = models.JSONField(default=dict)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("subject",)

class PolicyLogic(models.Model):
    class RuleType(models.TextChoices):
        PARTICIPANT = "participant", _("Participant")
        SERVICE = "service", _("Service")

    rule = models.ForeignKey(
        PolicyProxyRule,
        on_delete=models.CASCADE,
        related_name="advanced_logic",
    )

    rule_type = models.CharField(max_length=20, choices=RuleType.choices)
    enabled = models.BooleanField(default=False)

    conditions = models.JSONField(default=default_conditions, blank=True)
    response = models.JSONField(default=default_response, blank=True)

    reject_reason = models.CharField(max_length=255, blank=True, default="")
    description = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        unique_together = (("rule", "rule_type"),)
        indexes = [models.Index(fields=["rule", "rule_type"])]

    def __str__(self):
        return f"{self.rule.name} [{self.rule_type}]"
