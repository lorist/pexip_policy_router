from django.db import models
from django.core.exceptions import ValidationError
import json

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

    def clean(self):
        """Ensure DB consistency between checkboxes and JSON fields."""
        if not self.always_continue_service:
            self.override_service_response = None
        elif self.override_service_response in (None, "", {}):
            self.override_service_response = {"status": "success", "action": "continue"}

        if not self.always_continue_participant:
            self.override_participant_response = None
        elif self.override_participant_response in (None, "", {}):
            self.override_participant_response = {"status": "success", "action": "continue"}

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

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.created_at}] {self.request_method} {self.request_path}"

