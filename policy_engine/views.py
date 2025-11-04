import json, logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django.urls import reverse
from .schema import SERVICE_CALL_INFO_SCHEMA, PARTICIPANT_CALL_INFO_SCHEMA, PARTICIPANT_RESPONSE_SCHEMA, SERVICE_RESPONSE_SCHEMA
from policy_router.models import PolicyProxyRule, PolicyRequestLog
from .models import PolicyLogic, IdentityAttribute
from .forms import PolicyLogicForm
from .utils import evaluate_conditions, apply_template, normalize_policy_response, evaluate_single_condition, get_nested
from django.utils.safestring import mark_safe


logger = logging.getLogger("policy_engine.views")

# can probably get rid of this and the url when dev is finished
from django.views.decorators.csrf import csrf_exempt
@csrf_exempt
def test_signal(request):
    rule = PolicyProxyRule.objects.first()
    logic, created = PolicyLogic.objects.get_or_create(
        rule=rule,
        rule_type="service",
        defaults={"enabled": True},
    )

    # simulate update + delete to trigger both signals
    if created:
        action = "created"
    else:
        action = "already existed"

    # delete afterwards to test post_delete
    logic.delete()

    return JsonResponse({
        "message": f"Signal test complete — logic {action} then deleted",
        "rule_id": rule.id,
    })

@require_http_methods(["GET", "POST"])
def logic_editor(request, rule_id):
    from policy_engine.models import IdentityAttribute  # <-- Ensure this exists

    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)
    tab = request.GET.get("tab", "participant")

    participant_logic, _ = PolicyLogic.objects.get_or_create(rule=rule, rule_type="participant")
    service_logic, _ = PolicyLogic.objects.get_or_create(rule=rule, rule_type="service")

    participant_form = PolicyLogicForm(request.POST or None, instance=participant_logic, prefix="participant")
    service_form = PolicyLogicForm(request.POST or None, instance=service_logic, prefix="service")

    # -------------------------------------------------------
    # Normalize response builder JSON (unchanged)
    # -------------------------------------------------------
    def _normalize_builder_payload(raw_json: str | None) -> dict:
        """
        Ensure the response builder JSON is wrapped into
        {status, action, result: {...}} without discarding list or dict fields.
        """
        try:
            parsed = json.loads((raw_json or "").strip() or "{}")
        except Exception:
            parsed = {}

        # If already normalized, return as-is
        if isinstance(parsed, dict) and "status" in parsed and "action" in parsed:
            return parsed

        # NEW: Accept either {result:{...}} or just { ... }
        if isinstance(parsed, dict) and "result" in parsed and isinstance(parsed["result"], dict):
            result = parsed["result"]
        else:
            result = parsed if isinstance(parsed, dict) else {}

        return {
            "status": "success",
            "action": "continue",
            "result": result,
        }


    # -------------------------------------------------------
    # Save POST changes
    # -------------------------------------------------------
    if request.method == "POST":
        logic_type = request.POST.get("logic_type")  # "participant" or "service"
        logic = participant_logic if logic_type == "participant" else service_logic
        form = participant_form if logic_type == "participant" else service_form
        chosen_action = request.POST.get(f"{logic_type}_action", "allow")

        if form.is_valid():
            # -------------------------------
            # Conditions
            # -------------------------------
            raw_conditions = request.POST.get(f"{logic_type}_conditions", "").strip()
            logic.conditions = json.loads(raw_conditions or '{"combiner": "all", "rules": []}')
            logic.enabled = form.cleaned_data["enabled"]
            logic.description = form.cleaned_data["description"]

            reject_reason = (form.cleaned_data.get("reject_reason") or "").strip()

            # -------------------------------
            # Reject
            # -------------------------------
            if chosen_action == "reject":
                logic.reject_reason = reject_reason
                logic.response = {
                    "status": "success",
                    "action": "reject",
                    "result": {"reject_reason": reject_reason or "Call rejected"}
                }

            # -------------------------------
            # Redirect
            # -------------------------------
            elif chosen_action == "redirect":
                new_alias = request.POST.get("service_new_alias", "").strip()
                logic.response = {
                    "status": "success",
                    "action": "redirect",
                    "result": {"new_alias": new_alias}
                }

            # -------------------------------
            # Allow (Response Builder)
            # -------------------------------
            else:
                logic.reject_reason = ""
                raw_response = request.POST.get(f"{logic_type}_response_json", "").strip()
                payload = _normalize_builder_payload(raw_response)

                # Preserve list fields (including automatic_participants)
                if isinstance(payload, dict) and "result" in payload and isinstance(payload["result"], dict):
                    logic.response = payload
                else:
                    logic.response = {
                        "status": "success",
                        "action": "continue",
                        "result": payload,
                    }

            # Freeze JSON so lists cannot collapse to {}
            logic.response = json.loads(json.dumps(logic.response))

            logic.save()
            return redirect(f"{reverse('policy_engine:logic_editor', args=[rule.id])}?tab={logic_type}")

    # -------------------------------------------------------
    # Recent call info
    # -------------------------------------------------------
    recent_logs = (
        PolicyRequestLog.objects.filter(rule=rule)
        .exclude(request_params=None)
        .order_by("-created_at")[:20]
    )

    def extract_call_info(log):
        params = log.request_params or {}
        idp_attrs = {k.replace("idp_attribute_", ""): v for k, v in params.items() if k.startswith("idp_attribute_") and v}
        result = {**params}
        if idp_attrs:
            result["idp_attributes"] = idp_attrs
        return {"label": (result.get("remote_display_name") or result.get("local_alias") or "(unknown)"), "json": json.dumps(result, indent=2)}

    recent_call_info_list = [extract_call_info(log) for log in recent_logs]

    # -------------------------------------------------------
    # Field Value Suggestions
    # -------------------------------------------------------
    from collections import defaultdict

    def flatten(params):
        for k, v in params.items():
            if k.startswith("idp_attribute_"):
                yield f"idp_attributes.{k.replace('idp_attribute_', '')}", v
            else:
                yield k, v

    def is_participant(params):
        return any(k in params for k in ("participant_uuid", "participant_type", "preauthenticated_role"))

    participant_field_values = defaultdict(set)
    service_field_values = defaultdict(set)

    for log in recent_logs:
        params = log.request_params or {}
        for key, value in flatten(params):
            values = value if isinstance(value, list) else [value]
            cleaned = [str(x) for x in values if x not in ("", None)]
            if is_participant(params):
                participant_field_values[key].update(cleaned)
            else:
                service_field_values[key].update(cleaned)

    participant_field_values = {k: sorted(v) for k, v in participant_field_values.items()}
    service_field_values = {k: sorted(v) for k, v in service_field_values.items()}

    # -------------------------------------------------------
    # AVAILABLE VARIABLES (Configured + Learned + Response Keys)
    # -------------------------------------------------------
    configured = {f"idp_attributes.{x}" for x in IdentityAttribute.objects.values_list("name", flat=True)}

    participant_available_vars = set(configured)
    service_available_vars = set(configured)

    # Add all base schema-defined call_info fields
    participant_available_vars.update(PARTICIPANT_CALL_INFO_SCHEMA.keys())
    service_available_vars.update(SERVICE_CALL_INFO_SCHEMA.keys())

    # Make dotted idp_attributes.* resolve properly
    participant_available_vars.update(f"idp_attributes.{x}" for x in IdentityAttribute.objects.values_list("name", flat=True))
    service_available_vars.update(f"idp_attributes.{x}" for x in IdentityAttribute.objects.values_list("name", flat=True))
    def iter_keys(params):
        for k in params.keys():
            if k.startswith("idp_attribute_"):
                yield f"idp_attributes.{k.replace('idp_attribute_', '')}"
            else:
                yield k

    for log in recent_logs:
        params = log.request_params or {}
        keys = set(iter_keys(params))
        if is_participant(params):
            participant_available_vars.update(keys)
        else:
            service_available_vars.update(keys)

    def collect_vars(data, target):
        if isinstance(data, dict):
            for k, v in data.items():
                target.add(k)
                collect_vars(v, target)
        elif isinstance(data, list):
            for item in data:
                collect_vars(item, target)

    collect_vars(participant_logic.response, participant_available_vars)
    collect_vars(service_logic.response, service_available_vars)

    participant_available_vars = sorted(participant_available_vars)
    service_available_vars = sorted(service_available_vars)

    # -------------------------------------------------------
    # Example Values
    # -------------------------------------------------------
    example_values = {}
    for log in recent_logs:
        for k, v in (log.request_params or {}).items():
            val = v[0] if isinstance(v, list) and v else v
            if val:
                example_values.setdefault(k, set()).add(str(val))
    example_values = {k: sorted(v) for k, v in example_values.items()}

    # -------------------------------------------------------
    # Condition Schema + UI Mode
    # -------------------------------------------------------
    def to_field_list(schema, extra):
        fields = [{"name": n, "label": d.get("label", n.replace("_", " ").title()), "type": d.get("type", "string")} for n, d in schema.items()]
        for key in sorted(extra):
            fields.append({"name": key, "label": key, "type": "string"})
        return {"fields": fields}

    def get_mode(logic):
        action = (logic.response or {}).get("action", "continue")
        return "reject" if action == "reject" else "redirect" if action == "redirect" else "allow"

    context = {
        "rule": rule,
        "tab": tab,
        "participant_form": participant_form,
        "service_form": service_form,
        "participant_logic": participant_logic,
        "service_logic": service_logic,
        "participant_mode": get_mode(participant_logic),
        "service_mode": get_mode(service_logic),
        "participant_condition_schema": mark_safe(json.dumps(to_field_list(PARTICIPANT_CALL_INFO_SCHEMA, participant_available_vars))),
        "service_condition_schema": mark_safe(json.dumps(to_field_list(SERVICE_CALL_INFO_SCHEMA, service_available_vars))),
        "participant_conditions_json": json.dumps(participant_logic.conditions),
        "service_conditions_json": json.dumps(service_logic.conditions),
        "participant_response_json": json.dumps(participant_logic.response),
        "service_response_json": json.dumps(service_logic.response),
        "participant_response_schema": mark_safe(json.dumps(PARTICIPANT_RESPONSE_SCHEMA)),
        "service_response_schema": mark_safe(json.dumps(SERVICE_RESPONSE_SCHEMA)),
        "recent_call_info_list": recent_call_info_list,
        "participant_field_values": mark_safe(json.dumps(participant_field_values)),
        "service_field_values": mark_safe(json.dumps(service_field_values)),
        "participant_available_vars": participant_available_vars,
        "service_available_vars": service_available_vars,
        "call_info_example_values": example_values,
    }

    return render(request, "policy_engine/logic_editor.html", context)


@csrf_exempt
@require_POST
def preview_response(request, rule_id):
    """
    Preview what the logic response *would* produce for a given call_info.
    Does NOT modify rules or affect live policy decisions.
    """
    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    logic_type = data.get("type")  # "participant" or "service"
    conditions = data.get("conditions") or {}
    response_template = data.get("response") or {}
    call_info = data.get("call_info") or {}

    # Step 1 — Evaluate conditions
    match_result = evaluate_conditions(conditions, call_info)

    if match_result["matched"]:
        # Step 2 — Apply Jinja2 templating
        rendered = apply_template(response_template, call_info)
    else:
        rendered = {
            "action": "continue",
            "reason": "conditions_not_matched",
            "failed": match_result["failed_conditions"],
        }

    # Step 3 — Ensure valid Pexip response structure
    rendered = normalize_policy_response(rendered)

    return JsonResponse(
        {
            "matched": match_result["matched"],
            "rendered_response": rendered,
        },
        status=200
    )


@require_POST
@csrf_exempt
def logic_preview(request, rule_id):
    data = json.loads(request.body or "{}")

    logic_type = data.get("type")
    conditions = data.get("conditions") or {}
    response_template = data.get("response") or {}
    call_info = data.get("call_info") or {}

    # Evaluate conditions with detailed trace
    match = evaluate_conditions(conditions, call_info)

    # ✅ Build per-condition explanation tree
    from .utils import explain_condition
    explanation = []

    def walk(group, path="root"):
        for idx, rule in enumerate(group.get("rules", [])):
            if "rules" in rule:
                walk(rule, f"{path}.{idx}")
            else:
                explanation.append(explain_condition(rule["field"], rule["operator"], rule["value"], call_info))

    walk(conditions)

    # Build rendered result
    if match["matched"]:
        # If reject reason present — override to reject
        if logic_type == "participant":
            logic_obj = PolicyLogic.objects.get(rule_id=rule_id, rule_type="participant")
        else:
            logic_obj = PolicyLogic.objects.get(rule_id=rule_id, rule_type="service")

        if getattr(logic_obj, "reject_reason", "").strip():
            rendered = {
                "status": "success",
                "action": "reject",
                "result": {"reject_reason": logic_obj.reject_reason}
            }
        else:
            rendered = apply_template(response_template, call_info)

    else:
        rendered = {"action": "continue", "reason": "conditions_not_matched"}

    rendered = normalize_policy_response(rendered)
    return JsonResponse({
        "matched": match["matched"],
        "rendered_response": rendered,
        "explanation": explanation,
    }, status=200)

@require_POST
@csrf_exempt
def condition_preview(request, rule_id):
    """
    Preview a SINGLE condition row against Test Call Info.
    """
    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    field = data.get("field")
    operator = data.get("operator")
    value = data.get("value")
    call_info = data.get("call_info") or {}

    if not field or not operator:
        return JsonResponse({"error": "Missing field or operator"}, status=400)

    actual = get_nested(call_info, field)

    matched = evaluate_single_condition(actual, operator, value, call_info)

    return JsonResponse({
        "matched": bool(matched),
        "field": field,
        "operator": operator,
        "value": value,
        "actual": actual,
    }, status=200)