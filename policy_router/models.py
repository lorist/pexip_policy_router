from django.db import models


class PolicyProxyRule(models.Model):
    name = models.CharField(max_length=100, help_text="Friendly name for this routing rule")
    regex = models.CharField(
        max_length=255,
        help_text="Regex used to match against local_alias in incoming request"
    )
    service_target_url = models.URLField(
        blank=True, null=True,
        help_text="Base URL of the upstream service policy server"
    )
    participant_target_url = models.URLField(
        blank=True, null=True,
        help_text="Base URL of the upstream participant policy server"
    )
    is_active = models.BooleanField(default=True, help_text="Whether this rule is enabled")

    # Lower numbers = higher priority
    priority = models.IntegerField(
        default=100,
        help_text="Priority of the rule (lower values evaluated first)"
    )

    basic_auth_username = models.CharField(
        max_length=255, blank=True, null=True, help_text="Optional username for Basic Auth"
    )
    basic_auth_password = models.CharField(
        max_length=255, blank=True, null=True, help_text="Optional password for Basic Auth"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "updated_at"]  # Lowest first

    def __str__(self):
        return f"[{self.priority}] {self.name} (regex: {self.regex})"



class PolicyRequestLog(models.Model):
    rule = models.ForeignKey(PolicyProxyRule, on_delete=models.SET_NULL, null=True, blank=True)
    request_method = models.CharField(max_length=10)
    request_path = models.TextField()
    request_body = models.TextField(blank=True, null=True)
    response_status = models.IntegerField()
    response_body = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.response_status}] {self.request_method} {self.request_path}"
