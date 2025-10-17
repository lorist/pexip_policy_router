from django.db import models
from django.core.exceptions import ValidationError
import json
import re

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

    # Filters
    regex = models.CharField(max_length=255, help_text="Local alias regex to match incoming requests")

    protocols = models.JSONField(default=list, blank=True, null=True)
    call_directions = models.JSONField(default=list, blank=True, null=True)
    
    # Upstream targets
    service_target_url = models.URLField(blank=True, null=True)
    participant_target_url = models.URLField(blank=True, null=True)

    # Overrides
    always_continue_service = models.BooleanField(default=False, help_text="Always return continue for service policy")
    override_service_response = models.JSONField(null=True, blank=True, default=None)

    always_continue_participant = models.BooleanField(default=False, help_text="Always return continue for participant policy")
    override_participant_response = models.JSONField(null=True, blank=True, default=None)

    # Authentication
    basic_auth_username = models.CharField(max_length=255, blank=True, null=True)
    basic_auth_password = models.CharField(max_length=255, blank=True, null=True)

    # Management
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
        help_text="Optional source IP or FQDN of the Infinity node. "
                  "Leave blank to match any source."
    )
    source_host = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Source IP or FQDN of the requesting Infinity node"
    )

    def clean(self):
        """Ensure DB consistency and detect duplicate or overlapping regex patterns."""
        import re
        import random
        from django.core.exceptions import ValidationError

        # --- Keep JSON consistency logic ---
        if not self.always_continue_service:
            self.override_service_response = None
        elif self.override_service_response in (None, "", {}):
            self.override_service_response = {"status": "success", "action": "continue"}

        if not self.always_continue_participant:
            self.override_participant_response = None
        elif self.override_participant_response in (None, "", {}):
            self.override_participant_response = {"status": "success", "action": "continue"}

        # --- Validate regex syntax ---
        try:
            this_regex = re.compile(self.regex)
        except re.error as e:
            raise ValidationError({"regex": f"Invalid regex pattern: {e}"})

        # --- Smarter overlap detection ---
        overlapping = []
        # Generate test candidates likely to hit common alias shapes
        test_samples = [
            "room-1", "room-12", "room-123", "room-9999",
            "vmr-01", "vmr-999", "test", "room-", "conference-01",
        ]
        # Add some random variations to broaden matching
        for i in range(10):
            test_samples.append(f"room-{random.randint(0,9999)}")
            test_samples.append(f"vmr-{random.randint(0,9999)}")

        for other in type(self).objects.exclude(pk=self.pk).filter(is_active=True):
            try:
                other_regex = re.compile(other.regex)
            except re.error:
                continue

            # Skip exact duplicates
            if other.regex == self.regex:
                overlapping.append(other.name)
                continue

            # Check if both regexes match any of the same samples
            for sample in test_samples:
                if this_regex.search(sample) and other_regex.search(sample):
                    overlapping.append(other.name)
                    break

        if overlapping:
            raise ValidationError({
                "regex": (
                    f"This pattern may overlap or duplicate existing rule(s): "
                    f"{', '.join(set(overlapping))}"
                )
            })


        def __str__(self):
            return self.name



class PolicyRequestLog(models.Model):
    rule = models.ForeignKey(PolicyProxyRule, on_delete=models.SET_NULL, null=True, blank=True)
    request_method = models.CharField(max_length=10)
    request_path = models.TextField()
    request_body = models.TextField(null=True, blank=True)
    response_status = models.IntegerField()
    response_body = models.TextField(null=True, blank=True)
    is_override = models.BooleanField(default=False)

    # New fields for better filtering
    call_direction = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[("dial_in", "Dial In"), ("dial_out", "Dial Out"), ("non_dial", "Non Dial")],
    )
    protocol = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[
            ("api", "API"),
            ("webrtc", "WebRTC"),
            ("sip", "SIP"),
            ("rtmp", "RTMP"),
            ("h323", "H.323"),
            ("teams", "Teams"),
            ("mssip", "MS-SIP"),
        ],
    )

    source_host = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Source IP or FQDN of the requesting Infinity node",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.created_at}] {self.request_method} {self.request_path}"

