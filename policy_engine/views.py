import json, logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django.urls import reverse
from .schema import SERVICE_CALL_INFO_SCHEMA, PARTICIPANT_CALL_INFO_SCHEMA, PARTICIPANT_RESPONSE_SCHEMA
from policy_router.models import PolicyProxyRule
from .models import PolicyLogic
from .forms import PolicyLogicForm
from .utils import evaluate_conditions


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

    participant_logic, _ = PolicyLogic.objects.get_or_create(
        rule=rule,
        rule_type="participant",
        defaults={"enabled": False, "conditions": {}, "response": {}},
    )
    service_logic, _ = PolicyLogic.objects.get_or_create(
        rule=rule,
        rule_type="service",
        defaults={"enabled": False, "conditions": {}, "response": {}},
    )

    participant_form = PolicyLogicForm(
        request.POST or None, instance=participant_logic, prefix="participant"
    )
    service_form = PolicyLogicForm(
        request.POST or None, instance=service_logic, prefix="service"
    )

    def ensure_json(data):
        """Return a valid JSON string regardless of input type."""
        if isinstance(data, str):
            try:
                data = json.loads(data.replace("'", '"'))
            except json.JSONDecodeError:
                return "{}"
        return json.dumps(data or {})

    # -----------------------
    # Handle POST
    # -----------------------
    if request.method == "POST":
        target = request.POST.get("logic_type")
        print("🧠 POST keys:", list(request.POST.keys()))

        if target == "participant":
            form = participant_form
            hidden_data = request.POST.get("participant_conditions", "{}")
            logic_instance = participant_logic
        else:
            form = service_form
            hidden_data = request.POST.get("service_conditions", "{}")
            logic_instance = service_logic

        print(f"🔍 {target}_conditions =", hidden_data)

        if form.is_valid():
            # Save regular fields
            form.save(commit=False)

            # Save JSON logic safely
            try:
                parsed = json.loads(hidden_data)
                logic_instance.conditions = parsed
            except json.JSONDecodeError:
                logger.warning("⚠️ Invalid JSON for %s conditions", target)
                logic_instance.conditions = {}

            logic_instance.save()
            logger.info("💾 Saved %s logic for rule %s", target, rule.id)

            # Redirect back to correct tab (optional)
            return redirect(f"{reverse('policy_engine:logic_editor', args=[rule.id])}?tab={target}")

    # -----------------------
    # Render page
    # -----------------------
    context = {
        "rule": rule,
        "tab": tab,
        "participant_logic": participant_logic,
        "service_logic": service_logic,
        "participant_form": participant_form,
        "service_form": service_form,
        "service_schema": json.dumps(SERVICE_CALL_INFO_SCHEMA),
        "participant_schema": json.dumps(PARTICIPANT_CALL_INFO_SCHEMA),
        "participant_conditions_json": ensure_json(participant_logic.conditions),
        "participant_response_schema": json.dumps(PARTICIPANT_RESPONSE_SCHEMA),
        "service_conditions_json": ensure_json(service_logic.conditions),
    }

    logger.debug(
        "Logic editor opened for rule %s (participant_id=%s, service_id=%s)",
        rule.id,
        participant_logic.id,
        service_logic.id,
    )
    return render(request, "policy_engine/logic_editor.html", context)



@csrf_exempt
@require_POST
def preview_logic(request, rule_id):
    """
    Evaluate the current logic configuration against an optional call_info payload.
    Supports nested AND/OR groups.
    """
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)

    try:
        payload = json.loads(request.body.decode("utf-8"))
        logic_type = payload.get("logic_type")
        call_info = payload.get("call_info", {})
        conditions = payload.get("conditions", {})
        response = payload.get("response", {})

        logger.debug("Preview request: rule=%s type=%s", rule.id, logic_type)

        # Evaluate nested conditions recursively
        result = evaluate_conditions(conditions, call_info)

        logger.debug("Preview result: %s", result)

        return JsonResponse({
            "success": True,
            "result": {
                "matched": result["matched"],
                "failed_conditions": result["failed_conditions"],
                "evaluated_response": response if result["matched"] else {},
            },
        })

    except Exception as e:
        logger.exception("Preview logic error: %s", e)
        return JsonResponse({"success": False, "error": str(e)}, status=400)