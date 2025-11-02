from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError
import re
import random


class PolicyProxyRule(models.Model):
    PROTOCOL_CHOICES = [
        ("api", "API"),
        ("webrtc", "WebRTC"),
        ("sip", "SIP"),
        ("rtmp", "RTMP"),
        ("h323", "H.323"),
        ("teams", "Microsoft Teams"),
        ("mssip", "Microsoft SIP"),
    ]

    CALL_DIRECTION_CHOICES = [
        ("dial_in", "Dial In"),
        ("dial_out", "Dial Out"),
        ("non_dial", "Non Dial"),
    ]

    name = models.CharField(max_length=100, help_text="Friendly name for this routing rule")
    regex = models.CharField(max_length=255, help_text="Local alias regex to match incoming requests")

    protocols = models.JSONField(default=list, blank=True, null=True)
    call_directions = models.JSONField(default=list, blank=True, null=True)

    service_target_url = models.URLField(blank=True, null=True)
    participant_target_url = models.URLField(blank=True, null=True)

    always_continue_service = models.BooleanField(default=False, help_text="Always return continue for service policy")
    override_service_response = models.JSONField(null=True, blank=True, default=None)

    always_continue_participant = models.BooleanField(default=False, help_text="Always return continue for participant policy")
    override_participant_response = models.JSONField(null=True, blank=True, default=None)

    basic_auth_username = models.CharField(max_length=255, blank=True, null=True)
    basic_auth_password = models.CharField(max_length=255, blank=True, null=True)

    priority = models.IntegerField(default=100, help_text="Lower numbers match first")
    is_active = models.BooleanField(default=True)
    match_count = models.PositiveIntegerField(default=0)
    last_matched_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    source_match = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Optional source IP/FQDN. Leave blank to match any source.",
    )

    source_host = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Source host seen from request logs",
    )

    advanced_logic_enabled = models.BooleanField(
        default=False,
        help_text="Enable advanced logic editor (participant & service policies)."
    )

    def get_advanced_logic_url(self):
        return reverse("policy_engine:logic_editor", args=[self.id])

    # ✅ Correct rule conflict logic
    def clean(self):
        super().clean()

        # Validate regex syntax
        try:
            this_regex = re.compile(self.regex)
        except re.error as e:
            raise ValidationError({"regex": f"Invalid regex pattern: {e}"})

        # Normalize source_match
        if self.source_match:
            sm = self.source_match.strip().lower()
            if sm in ("", "none", "null"):
                self.source_match = None
            else:
                self.source_match = sm
        else:
            self.source_match = None

        # ✅ Determine scope: service or participant (used for conflict resolution)
        self_scope = (
            "service" if self.always_continue_service else
            "participant" if self.always_continue_participant else
            None
        )

        # ✅ Only block duplicates when: regex + source_match + priority + scope all match
        if self.regex and self.source_match:
            qs = type(self).objects.filter(
                regex=self.regex,
                source_match=self.source_match,
                is_active=True
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)

            for other in qs:
                other_scope = (
                    "service" if other.always_continue_service else
                    "participant" if other.always_continue_participant else
                    None
                )
                same_priority = other.priority == self.priority
                same_scope = self_scope == other_scope

                if same_priority and same_scope:
                    raise ValidationError({
                        "regex": (
                            "A rule already exists with the same regex, "
                            "source_match, priority, and policy scope. "
                            "These policies would conflict."
                        )
                    })

    def save(self, *args, **kwargs):
        self.full_clean()  # ensure logic always enforced
        return super().save(*args, **kwargs)


class PolicyRequestLog(models.Model):
    rule = models.ForeignKey(PolicyProxyRule, on_delete=models.SET_NULL, null=True, blank=True)
    request_method = models.CharField(max_length=10)
    request_path = models.TextField()
    request_params = models.JSONField(null=True, blank=True)
    response_status = models.IntegerField()
    response_body = models.TextField(null=True, blank=True)
    is_override = models.BooleanField(default=False)

    call_direction = models.CharField(max_length=20, blank=True, null=True)
    protocol = models.CharField(max_length=20, blank=True, null=True)
    source_host = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    matched_logic = models.BooleanField(default=False)
    logic_response = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"[{self.created_at}] {self.request_method} {self.request_path}"
