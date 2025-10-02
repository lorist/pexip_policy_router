from django.contrib import admin
from .models import PolicyProxyRule, PolicyRequestLog


@admin.register(PolicyProxyRule)
class PolicyProxyRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "regex", "service_target_url", "participant_target_url", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "regex", "service_target_url", "participant_target_url")


@admin.register(PolicyRequestLog)
class PolicyRequestLogAdmin(admin.ModelAdmin):
    list_display = ("id", "rule", "request_method", "request_path", "response_status", "created_at")
    list_filter = ("response_status", "created_at")
    search_fields = ("request_path", "response_body")
