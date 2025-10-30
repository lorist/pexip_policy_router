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
from .utils import evaluate_conditions
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

    # -----------------------
    # Handle POST
    # -----------------------
    if request.method == "POST":
        logic_type = request.POST.get("logic_type")
        logic = participant_logic if logic_type == "participant" else service_logic
        form = participant_form if logic_type == "participant" else service_form

        if form.is_valid():
            # --- SAFE CONDITIONS LOADING ---
            raw_conditions = request.POST.get(f"{logic_type}_conditions", "").strip()
            if not raw_conditions:
                raw_conditions = '{"combiner": "all", "rules": []}'
            logic.conditions = json.loads(raw_conditions)

            # --- SAFE RESPONSE LOADING ---
            raw_response = request.POST.get(f"{logic_type}_response_json", "").strip()
            if not raw_response:
                raw_response = '{"action": "continue"}'
            logic.response = json.loads(raw_response)
            logic.enabled = form.cleaned_data["enabled"]
            logic.description = form.cleaned_data["description"]
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
        data = {
            "call_direction": params.get("call_direction") or log.call_direction,
            "protocol": params.get("protocol") or log.protocol,
            "source_host": log.source_host,
            "alias": params.get("alias"),
            "vendor": params.get("vendor"),
            "bandwidth": params.get("bandwidth"),
        }
        return {k: v for k, v in data.items() if v is not None}

    recent_call_info_list = [
        {
            "label": f"{ci.get('alias') or '(unknown)'} — {ci.get('call_direction')} — {ci.get('protocol')}",
            "json": json.dumps(ci, default=str),
        }
        for ci in (extract_call_info(log) for log in recent_logs)
    ]

    # -----------------------
    # Field Value Autosuggest Sets
    # -----------------------
    def extract_enums(schema):
        return {
            field: details.get("enum", [])
            for field, details in schema.items()
            if isinstance(details, dict) and "enum" in details
        }
    
    def to_field_list(schema):
        fields = []
        for name, props in schema.items():
            fields.append({
                "name": name,
                "label": name.replace("_", " ").title(),
                "type": props.get("type", "string"),
            })
        return {"fields": fields}

    def normalize_schema(schema):
        fields = []
        for field, details in schema.items():
            label = details.get("label", field.replace("_", " ").title())
            enum = details.get("enum", [])
            fields.append({
                "name": field,
                "label": label,
                "type": details.get("type", "string"),
                "choices": enum,
            })
        return {"fields": fields}

    participant_field_values = extract_enums(PARTICIPANT_CALL_INFO_SCHEMA)
    service_field_values = extract_enums(SERVICE_CALL_INFO_SCHEMA)

    for log in recent_logs:
        p = log.request_params or {}
        for field, value in p.items():
            participant_field_values.setdefault(field, set()).add(value)

    participant_field_values = {k: sorted(v) if isinstance(v, set) else v for k, v in participant_field_values.items()}
    service_field_values = {k: sorted(v) if isinstance(v, set) else v for k, v in service_field_values.items()}

    # -----------------------
    # Final Context
    # -----------------------
    context = {
        "rule": rule,
        "tab": tab,
        "participant_form": participant_form,
        "service_form": service_form,
        "participant_logic": participant_logic,
        "service_logic": service_logic,

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
    }

    return render(request, "policy_engine/logic_editor.html", context)




@csrf_exempt
@require_POST
def preview_logic(request, rule_id):
    """
    Returns the response that WOULD be returned for a given call_info
    without saving or affecting the rule.
    """
    data = json.loads(request.body or "{}")

    logic_type = data.get("type")  # "participant" or "service"
    conditions = data.get("conditions") or {}
    response = data.get("response") or {}
    call_info = data.get("call_info") or {}

    match_result = evaluate_conditions(conditions, call_info)

    if match_result["matched"]:
        result = response
    else:
        result = {
            "action": "continue",
            "reason": "conditions_not_matched",
            "failed": match_result["failed_conditions"],
        }

    return JsonResponse({"result": result}, status=200)

@require_POST
@csrf_exempt
def logic_preview(request, rule_id):
    """
    Evaluate logic for previewing conditions and response.
    Returns the `response` if conditions match, else {}.
    Does NOT modify the database.
    """
    data = json.loads(request.body.decode("utf-8"))

    logic_type = data.get("type")
    conditions = data.get("conditions", {})
    response = data.get("response", {})
    call_info = data.get("call_info", {}) or {}

    # Resolve correct stored logic object (if needed in future)
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)

    try:
        logic = rule.advanced_logics.get(rule_type=logic_type)
    except PolicyLogic.DoesNotExist:
        logic = None

    # --- Simple evaluator ----------------------------------------------------
    def evaluate(group):
        combiner = group.get("combiner", "all")
        rules = group.get("rules", [])

        results = []
        for r in rules:
            # nested group case
            if "rules" in r:
                results.append(evaluate(r))
                continue

            field = r.get("field")
            operator = r.get("operator")
            value = r.get("value")

            actual = call_info.get(field)

            match = False
            if operator == "equals":
                match = actual == value
            elif operator == "not_equals":
                match = actual != value
            elif operator == "contains" and isinstance(actual, str):
                match = value in actual
            elif operator == "starts_with" and isinstance(actual, str):
                match = actual.startswith(value)
            elif operator == "ends_with" and isinstance(actual, str):
                match = actual.endswith(value)
            elif operator == "in_list" and isinstance(actual, (list, tuple)):
                match = value in actual

            results.append(match)

        return all(results) if combiner == "all" else any(results)

    # --- Apply test logic ----------------------------------------------------
    if evaluate(conditions):
        result = response
    else:
        result = {}

    return JsonResponse({"result": result})