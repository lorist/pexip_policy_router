import json, logging, os
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from policy_router.models import PolicyProxyRule
from policy_router.views import maybe_protected
from .models import PolicyLogic, PolicyDecisionLog
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)

# -----------------------------
# Load Service Field Schema
# -----------------------------
schema_path = os.path.join(settings.BASE_DIR, "policy_engine/schemas/service_fields_schema.json")
try:
    with open(schema_path) as f:
        SERVICE_SCHEMA = json.load(f)
except FileNotFoundError:
    logger.error("❌ Service schema not found at %s", schema_path)
    SERVICE_SCHEMA = {}

# -----------------------------
# Advanced Logic Editor
# -----------------------------
@require_http_methods(["GET", "POST"])
def logic_editor(request, rule_id):
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)
    participant_logic, _ = PolicyLogic.objects.get_or_create(rule=rule, rule_type=PolicyLogic.PARTICIPANT)
    service_logic, _ = PolicyLogic.objects.get_or_create(rule=rule, rule_type=PolicyLogic.SERVICE)

    # ----------------------------
    # Field choices by policy type
    # ----------------------------
    SERVICE_FIELDS = [
        ("call_direction", "Call Direction"),
        ("protocol", "Protocol"),
        ("bandwidth", "Bandwidth"),
        ("vendor", "Vendor"),
        ("encryption", "Encryption"),
        ("registered", "Registered"),
        ("trigger", "Trigger"),
        ("remote_display_name", "Remote Display Name"),
        ("remote_alias", "Remote Alias"),
        ("remote_address", "Remote Address"),
        ("remote_port", "Remote Port"),
        ("call_tag", "Call Tag"),
        ("idp_uuid", "IDP UUID"),
        ("has_authenticated_display_name", "Authenticated Display Name"),
        ("supports_direct_media", "Supports Direct Media"),
        ("teams_tenant_id", "Teams Tenant ID"),
        ("location", "Location"),
        ("node_ip", "Node IP"),
        ("version_id", "Version ID"),
        ("pseudo_version_id", "Pseudo Version ID"),
        ("local_alias", "Local Alias"),
    ]

    PARTICIPANT_FIELDS = SERVICE_FIELDS + [
        ("preauthenticated_role", "Preauthenticated Role"),
        ("bypass_lock", "Bypass Lock"),
        ("receive_from_audio_mix", "Receive From Audio Mix"),
        ("display_count", "Display Count"),
        ("participant_type", "Participant Type"),
        ("participant_uuid", "Participant UUID"),
        ("call_uuid", "Call UUID"),
        ("breakout_uuid", "Breakout UUID"),
        ("send_to_audio_mixes_mix_name", "Send to Audio Mix Name"),
        ("send_to_audio_mixes_prominent", "Send to Audio Mix Prominent"),
        ("unique_service_name", "Unique Service Name"),
        ("service_name", "Service Name"),
        ("service_tag", "Service Tag"),
    ]

    OPERATOR_CHOICES = [
        ("equals", "equals"),
        ("not_equals", "not equals"),
        ("contains", "contains"),
        ("not_contains", "not contains"),
        ("startswith", "starts with"),
        ("endswith", "ends with"),
    ]

    # ----------------------------
    # Handle POST
    # ----------------------------
    if request.method == "POST":
        overall_errors = False

        for key, instance in (("participant", participant_logic), ("service", service_logic)):
            enabled_value = request.POST.get(f"{key}_enabled", "off")
            instance.enabled = enabled_value == "on"
            instance.description = request.POST.get(f"{key}_description", "").strip()

            # collect conditions
            conditions = []
            total = int(request.POST.get(f"{key}_condition_total", "0"))
            for i in range(total):
                param = request.POST.get(f"{key}_param_{i}")
                operator = request.POST.get(f"{key}_op_{i}")
                value = request.POST.get(f"{key}_val_{i}")
                if param and operator:
                    conditions.append({"parameter": param, "operator": operator, "value": value})
            instance.conditions = {"match_mode": "all", "conditions": conditions}

            # ----------------------------
            # Handle service logic response
            # ----------------------------
            if key == "service":
                # Extract dynamic form data
                service_type = request.POST.get("service_type", "").strip()
                result_fields = {}

                if service_type in SERVICE_SCHEMA:
                    for field in SERVICE_SCHEMA[service_type]["fields"]:
                        key_name = field["key"]
                        value = request.POST.get(key_name)
                        if value not in (None, ""):
                            # Convert booleans and ints
                            if field["type"] == "boolean":
                                result_fields[key_name] = value.lower() == "true"
                            elif field["type"] == "integer":
                                try:
                                    result_fields[key_name] = int(value)
                                except ValueError:
                                    result_fields[key_name] = value
                            elif field["type"] == "list":
                                try:
                                    result_fields[key_name] = json.loads(value)
                                except json.JSONDecodeError:
                                    result_fields[key_name] = [v.strip() for v in value.split(",") if v.strip()]
                            else:
                                result_fields[key_name] = value

                    # Build the standard service response JSON
                    instance.response = {
                        "status": "success",
                        "action": "continue",
                        "result": result_fields
                    }
                else:
                    # fallback: raw JSON if user manually entered it
                    try:
                        instance.response = json.loads(request.POST.get(f"{key}_response", "{}"))
                    except json.JSONDecodeError as e:
                        messages.error(request, f"Service response JSON invalid: {e}")
                        overall_errors = True
            else:
                # participant logic: still parse manually from textarea
                try:
                    instance.response = json.loads(request.POST.get(f"{key}_response", "{}") or "{}")
                except json.JSONDecodeError as e:
                    messages.error(request, f"{key.title()} response JSON invalid: {e}")
                    overall_errors = True

            instance.save()

        if not overall_errors:
            messages.success(request, "Advanced logic saved.")
        else:
            messages.warning(request, "Saved with some validation errors.")

        return redirect("policy_router:rule_list")

    # ----------------------------
    # Render the editor form
    # ----------------------------
    # context = {
    #     "rule": rule,
    #     "participant": participant_logic,
    #     "service": service_logic,
    #     "participant_fields": json.dumps(PARTICIPANT_FIELDS),
    #     "service_fields": json.dumps(SERVICE_FIELDS),
    #     "operator_choices": json.dumps(OPERATOR_CHOICES),
    #      "service_schema": mark_safe(json.dumps(SERVICE_SCHEMA, indent=2)),
    # }
    context = {
        "rule": rule,
        "participant": participant_logic,
        "service": service_logic,
        "participant_fields": PARTICIPANT_FIELDS,
        "service_fields": SERVICE_FIELDS,
        "operator_choices": OPERATOR_CHOICES,
        "service_schema": SERVICE_SCHEMA,
    }
    return render(request, "policy_engine/logic_editor_form.html", context)


# -----------------------------
# Decision Log List
# -----------------------------
@maybe_protected
@require_http_methods(["GET"])
def logic_decision_log_list(request, rule_id):
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)
    logs = PolicyDecisionLog.objects.filter(rule_id=rule_id).order_by("-decided_at")
    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "policy_engine/logic_decision_logs.html",
        {"rule": rule, "logs": page_obj, "page_obj": page_obj},
    )


# -----------------------------
# Logic Overview Page
# -----------------------------
@maybe_protected
def logic_overview(request):
    logics = (
        PolicyLogic.objects
        .select_related("rule")
        .order_by("rule__priority", "rule__name", "rule_type")
    )
    return render(request, "policy_engine/logic_overview.html", {"logics": logics})
