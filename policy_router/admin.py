from django.contrib import admin
from .models import PolicyProxyRule, PolicyRequestLog


@admin.register(PolicyProxyRule)
class PolicyProxyRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "regex",
        "priority",
        "is_active",
        "service_target_url",
        "participant_target_url",
        "has_service_override",
        "has_participant_override",
        "updated_at",
    )
    list_filter = ("is_active",)
    list_editable = ("priority", "is_active")

    def has_service_override(self, obj):
        return bool(obj.override_service_response)
    has_service_override.boolean = True
    has_service_override.short_description = "Service Override"

    def has_participant_override(self, obj):
        return bool(obj.override_participant_response)
    has_participant_override.boolean = True
    has_participant_override.short_description = "Participant Override"


@admin.register(PolicyRequestLog)
class PolicyRequestLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "rule",
        "request_method",
        "request_path",
        "response_status",
        "is_override",
    )
    list_filter = ("response_status", "is_override", "created_at")
    search_fields = ("request_path", "request_body", "response_body")
