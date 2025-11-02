from django.contrib import admin
from .models import PolicyLogic
from django.utils.html import format_html
from django.urls import reverse


@admin.register(PolicyLogic)
class PolicyLogicAdmin(admin.ModelAdmin):
    list_display = ("id", "rule", "rule_type", "enabled", "short_desc")
    list_filter = ("rule_type", "enabled")
    search_fields = ("rule__name", "description")
    # autocomplete_fields = ("rule",)

    def advanced_logic_link(self, obj):
        url = reverse("policy_engine:logic_editor", args=[obj.id])
        return format_html('<a href="{}" class="button">🧠 Advanced Logic</a>', url)

    advanced_logic_link.short_description = "Advanced Logic"

    @admin.display(description="Description")
    def short_desc(self, obj: PolicyLogic):
        return (obj.description or "")[:60]
    
    # Only show PolicyLogic records tied to rules with advanced_logic_enabled=True
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(rule__advanced_logic_enabled=True)
