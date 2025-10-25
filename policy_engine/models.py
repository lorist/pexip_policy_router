from django.db import models
from django.utils import timezone
from policy_router.models import PolicyProxyRule

class PolicyLogic(models.Model):
    PARTICIPANT = 'participant'
    SERVICE = 'service'
    RULE_TYPE_CHOICES = [
        (PARTICIPANT, 'Participant'),
        (SERVICE, 'Service'),
    ]
    rule = models.ForeignKey(PolicyProxyRule, on_delete=models.CASCADE, related_name='advanced_logic')
    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES)
    enabled = models.BooleanField(default=True)
    conditions = models.JSONField(default=dict, blank=True)
    response = models.JSONField(default=dict, blank=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('rule', 'rule_type')
        ordering = ['rule_id', 'rule_type']

    def __str__(self):
        return f"{self.rule} [{self.rule_type}]"

class PolicyDecisionLog(models.Model):
    rule = models.ForeignKey(PolicyProxyRule, on_delete=models.CASCADE, related_name="decision_logs")
    rule_type = models.CharField(max_length=32, choices=[("service", "Service"), ("participant", "Participant")])
    matched = models.BooleanField(default=False)
    decided_at = models.DateTimeField(default=timezone.now)

    # Full request and response bodies
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)

    # context fields for traceability
    local_alias = models.CharField(max_length=256, blank=True, null=True)
    participant_uuid = models.CharField(max_length=128, blank=True, null=True)
    protocol = models.CharField(max_length=64, blank=True, null=True)
    call_direction = models.CharField(max_length=32, blank=True, null=True)
    remote_display_name = models.CharField(max_length=256, blank=True, null=True)
    remote_alias = models.CharField(max_length=256, blank=True, null=True)
    request_id = models.CharField(max_length=128, blank=True, null=True)

    # JSON representation of evaluated conditions or final response
    evaluation_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-decided_at']

    def __str__(self):
        state = 'MATCH' if self.matched else 'NO MATCH'
        return f"{self.rule} [{self.rule_type}] — {state} @ {self.decided_at:%Y-%m-%d %H:%M:%S}"
