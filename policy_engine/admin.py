from django.contrib import admin
from .models import PolicyLogic, PolicyDecisionLog

@admin.register(PolicyLogic)
class PolicyLogicAdmin(admin.ModelAdmin):
    list_display = ("rule", "rule_type", "enabled", "description", "updated_at")
    list_filter = ("rule_type", "enabled")
    search_fields = ("rule__name", "description")
    ordering = ("rule__name", "rule_type")


@admin.register(PolicyDecisionLog)
class PolicyDecisionLogAdmin(admin.ModelAdmin):
    list_display = (
        "decided_at",
        "rule",
        "rule_type",
        "matched",
        "local_alias",
        "participant_uuid",
        "protocol",
        "call_direction",
    )
    list_filter = ("rule_type", "matched", "protocol", "call_direction")
    search_fields = (
        "rule__name",
        "local_alias",
        "participant_uuid",
        "remote_display_name",
        "remote_alias",
        "request_id",
    )
    readonly_fields = (
        "decided_at",
        "rule",
        "rule_type",
        "matched",
        "request_payload",
        "response_payload",
        "local_alias",
        "participant_uuid",
        "protocol",
        "call_direction",
        "remote_display_name",
        "remote_alias",
        "request_id",
        "evaluation_summary",
    )
    ordering = ("-decided_at",)
    date_hierarchy = "decided_at"
