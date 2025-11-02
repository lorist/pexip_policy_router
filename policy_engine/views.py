import json, logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django.urls import reverse
from .schema import SERVICE_CALL_INFO_SCHEMA, PARTICIPANT_CALL_INFO_SCHEMA, PARTICIPANT_RESPONSE_SCHEMA, SERVICE_RESPONSE_SCHEMA
from policy_router.models import PolicyProxyRule, PolicyRequestLog
from .models import PolicyLogic
from .forms import PolicyLogicForm
from .utils import evaluate_conditions, apply_template, normalize_policy_response
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
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)
    tab = request.GET.get("tab", "participant")

    participant_logic, _ = PolicyLogic.objects.get_or_create(rule=rule, rule_type="participant")
    service_logic, _ = PolicyLogic.objects.get_or_create(rule=rule, rule_type="service")

    participant_form = PolicyLogicForm(request.POST or None, instance=participant_logic, prefix="participant")
    service_form = PolicyLogicForm(request.POST or None, instance=service_logic, prefix="service")

    def _normalize_builder_payload(raw_json: str | None) -> dict:
        """
        Accepts the JSON string coming from the response builder.
        Returns a dict in the strict Pexip shape:
        {"status":"success","action":"continue","result":{...}}
        Any top-level keys other than status/action/result are moved into result.
        """
        try:
            parsed = json.loads((raw_json or "").strip() or "{}")
        except Exception:
            parsed = {}

        if not isinstance(parsed, dict):
            parsed = {}

        # Start with an existing result if present and valid
        result = parsed.get("result")
        result = result if isinstance(result, dict) else {}

        # Move *all* non-reserved top-level keys into result
        for k, v in list(parsed.items()):
            if k not in ("status", "action", "result"):
                result[k] = v

        return {
            "status": "success",
            "action": "continue",
            "result": result,
        }

    # -----------------------
    # Handle POST
    # -----------------------
    if request.method == "POST":
        logic_type = request.POST.get("logic_type")  # "participant" or "service"
        logic = participant_logic if logic_type == "participant" else service_logic
        form = participant_form if logic_type == "participant" else service_form

        # The UI gives us participant_action or service_action
        action_field = f"{logic_type}_action"
        chosen_action = request.POST.get(action_field, "allow")  # default allow

        if form.is_valid():
            # Store conditions JSON
            raw_conditions = request.POST.get(f"{logic_type}_conditions", "").strip()
            logic.conditions = json.loads(raw_conditions or '{"combiner": "all", "rules": []}')

            # Store enable + description
            logic.enabled = form.cleaned_data["enabled"]
            logic.description = form.cleaned_data["description"]

            # Always store the reject reason field for UI state
            # Always store description & enabled
            logic.enabled = form.cleaned_data["enabled"]
            logic.description = form.cleaned_data["description"]

            # Clear reject reason unless action == reject
            reject_reason = (form.cleaned_data.get("reject_reason") or "").strip()
            if chosen_action == "reject":
                logic.reject_reason = reject_reason
            else:
                logic.reject_reason = ""
                
            if chosen_action == "reject":
                logic.response = {
                    "status": "success",
                    "action": "reject",
                    "result": {"reject_reason": reject_reason or "Call rejected"},
                }

            elif chosen_action == "redirect":
                new_alias = request.POST.get("service_new_alias", "").strip()
                logic.response = {
                    "status": "success",
                    "action": "redirect",
                    "result": {"new_alias": new_alias},
                }

            else:  # allow
                raw_response = request.POST.get(f"{logic_type}_response_json", "")
                logic.response = _normalize_builder_payload(raw_response)

            logic.save()
            return redirect(f"{reverse('policy_engine:logic_editor', args=[rule.id])}?tab={logic_type}")

    # -----------------------
    # Recent Call Info History
    # -----------------------
    recent_logs = (
        PolicyRequestLog.objects.filter(rule=rule)
        .exclude(request_params=None)
        .order_by("-created_at")[:20]
    )

    def extract_call_info(log):
        params = log.request_params or {}

        # Flatten idp_attribute_* into idp_attributes dict
        idp_attrs = {
            k.replace("idp_attribute_", ""): v
            for k, v in params.items()
            if k.startswith("idp_attribute_") and v not in (None, "", [])
        }

        result = {**params}
        if idp_attrs:
            result["idp_attributes"] = idp_attrs

        result["remote_display_name"] = (params.get("remote_display_name") or [""])[0]
        result["remote_alias"] = (params.get("remote_alias") or [""])[0]
        result["call_direction"] = (params.get("call_direction") or [""])[0] or log.call_direction
        result["protocol"] = (params.get("protocol") or [""])[0] or log.protocol

        label = (
            result.get("remote_display_name")
            or result.get("idp_attributes", {}).get("displayname")
            or result.get("idp_attributes", {}).get("mail")
            or result.get("local_alias", [""])[0]
            or "(unknown)"
        )

        summary = f"{label} — {result.get('call_direction', '?')} — {result.get('protocol', '?')}"

        return {"label": summary, "json": json.dumps(result, default=str, indent=2)}

    recent_call_info_list = [extract_call_info(log) for log in recent_logs]

    # -----------------------
    # Build Field Value Suggestions
    # -----------------------
    from collections import defaultdict

    def flatten_params(params):
        for k, v in params.items():
            if k.startswith("idp_attribute_"):
                yield f"idp_attributes.{k.replace('idp_attribute_', '')}", v
            else:
                yield k, v
    def is_participant_request(params):
        return any(
            k in params
            for k in ("participant_uuid", "participant_type", "preauthenticated_role")
        )
    
    participant_field_values = defaultdict(set)
    service_field_values = defaultdict(set)

    for log in recent_logs:
        params = log.request_params or {}
        for key, value in flatten_params(params):
            values = value if isinstance(value, list) else [value]
            cleaned = [str(x) for x in values if x not in ("", None)]

            # We can detect participant vs service request by presence of `service_type`
            if is_participant_request(params):
                participant_field_values[key].update(cleaned)
            else:
                service_field_values[key].update(cleaned)

    participant_field_values = {k: sorted(v) for k, v in participant_field_values.items()}
    service_field_values = {k: sorted(v) for k, v in service_field_values.items()}

    # -----------------------
    # Available Variable Lists
    # -----------------------
    def iter_keys(params):
        for k in params.keys():
            if k.startswith("idp_attribute_"):
                yield f"idp_attributes.{k.replace('idp_attribute_', '')}"
            else:
                yield k

    participant_available_vars = set()
    service_available_vars = set()

    for log in recent_logs:
        params = log.request_params or {}
        keys = set(iter_keys(params))

        if is_participant_request(params):
            participant_available_vars.update(keys)
        else:
            service_available_vars.update(keys)

    # Also pull keys used in saved responses:
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

    # -----------------------
    # Example Values
    # -----------------------
    example_values = {}
    for log in recent_logs:
        params = log.request_params or {}
        for key, value in params.items():
            if isinstance(value, list) and value:
                value = value[0]
            if value:
                example_values.setdefault(key, set()).add(str(value))

    example_values = {k: sorted(v) for k, v in example_values.items()}

    # def to_field_list(schema):
    #     return {"fields": [
    #         {"name": name, "label": name.replace("_", " ").title(), "type": props.get("type", "string")}
    #         for name, props in schema.items()
    #     ]}

    def to_field_list(schema):
        return {
            "fields": [
                {
                    "name": name,
                    "label": details.get("label", name.replace("_", " ").title()),
                    "type": details.get("type", "string")
                }
                for name, details in schema.items()
            ]
        }
    
    def get_mode(logic):
        action = (logic.response or {}).get("action", "continue")
        if action == "reject":
            return "reject"
        if action == "redirect":
            return "redirect"
        return "allow"  # default

    # Determine UI mode from stored response
    participant_mode = get_mode(participant_logic)
    service_mode = get_mode(service_logic)

    context = {
        "rule": rule,
        "tab": tab,

        "participant_form": participant_form,
        "service_form": service_form,
        "participant_logic": participant_logic,
        "service_logic": service_logic,

        "participant_mode": participant_mode,
        "service_mode": service_mode,

        "participant_condition_schema": mark_safe(json.dumps(to_field_list(PARTICIPANT_CALL_INFO_SCHEMA))),
        "service_condition_schema": mark_safe(json.dumps(to_field_list(SERVICE_CALL_INFO_SCHEMA))),

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
