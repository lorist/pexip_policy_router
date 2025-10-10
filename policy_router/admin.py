from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect
import csv, io
from .models import PolicyProxyRule, PolicyRequestLog
from .forms import CSVImportForm


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
    actions = ["export_as_csv"]

    change_list_template = "admin/policy_proxy_rule_changelist.html"  # adds import UI

    # --- Boolean indicators ---
    def has_service_override(self, obj):
        return bool(obj.override_service_response)
    has_service_override.boolean = True
    has_service_override.short_description = "Service Override"

    def has_participant_override(self, obj):
        return bool(obj.override_participant_response)
    has_participant_override.boolean = True
    has_participant_override.short_description = "Participant Override"

    # --- CSV export ---
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=policy_rules.csv"

        writer = csv.writer(response)
        writer.writerow([
            "name",
            "regex",
            "priority",
            "is_active",
            "service_target_url",
            "participant_target_url",
        ])
        for rule in queryset:
            writer.writerow([
                rule.name,
                rule.regex,
                rule.priority,
                rule.is_active,
                rule.service_target_url,
                rule.participant_target_url,
            ])
        return response
    export_as_csv.short_description = "Export selected rules as CSV"

    # --- CSV import ---
    def changelist_view(self, request, extra_context=None):
        if "import" in request.POST:
            form = CSVImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = io.TextIOWrapper(request.FILES["csv_file"].file, encoding="utf-8")
                reader = csv.DictReader(csv_file)
                count = 0
                for row in reader:
                    PolicyProxyRule.objects.update_or_create(
                        name=row["name"],
                        defaults={
                            "regex": row.get("regex", ""),
                            "priority": int(row.get("priority", 0)),
                            "is_active": row.get("is_active", "True").lower() in ("true", "1"),
                            "service_target_url": row.get("service_target_url", ""),
                            "participant_target_url": row.get("participant_target_url", ""),
                        },
                    )
                    count += 1
                self.message_user(request, f"Imported {count} rules.", messages.SUCCESS)
                return redirect(".")
        else:
            form = CSVImportForm()

        extra_context = extra_context or {}
        extra_context["csv_import_form"] = form
        return super().changelist_view(request, extra_context=extra_context)


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
