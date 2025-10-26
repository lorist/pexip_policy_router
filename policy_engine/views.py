import json, logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django.urls import reverse
from .schema import SERVICE_CALL_INFO_SCHEMA, PARTICIPANT_CALL_INFO_SCHEMA
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

    # instantiate forms separately
    participant_form = PolicyLogicForm(
        request.POST or None, instance=participant_logic, prefix="participant"
    )
    service_form = PolicyLogicForm(
        request.POST or None, instance=service_logic, prefix="service"
    )

    if request.method == "POST":
        target = request.POST.get("logic_type")
        form = participant_form if target == "participant" else service_form
        if form.is_valid():
            form.save()
            logger.info("Saved %s logic for rule %s", target, rule.id)

    context = {
        "rule": rule,
        "tab": tab,
        "participant_logic": participant_logic,
        "service_logic": service_logic,
        "participant_form": participant_form,
        "service_form": service_form,
        "service_schema": json.dumps(SERVICE_CALL_INFO_SCHEMA),
        "participant_schema": json.dumps(PARTICIPANT_CALL_INFO_SCHEMA),
    }
    logger.debug(
        "Logic editor opened for rule %s (participant_id=%s, service_id=%s)",
        rule.id,
        participant_logic.id,
        service_logic.id,
    )
    return render(request, "policy_engine/logic_editor.html", context)


@csrf_exempt  # frontend fetch can call directly (you can secure later)
@require_POST
def preview_logic(request, rule_id):
    """
    Evaluate the current logic configuration against an optional call_info payload.
    """
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)

    try:
        payload = json.loads(request.body.decode("utf-8"))
        logic_type = payload.get("logic_type")
        call_info = payload.get("call_info", {})
        conditions = payload.get("conditions", {})
        response = payload.get("response", {})

        logger.debug("Preview request: rule=%s type=%s", rule.id, logic_type)

        # --- Simulate evaluation logic ---
        match = True
        failed_conditions = []
        for key, expected in conditions.items():
            actual = call_info.get(key)
            if actual != expected:
                match = False
                failed_conditions.append({key: {"expected": expected, "actual": actual}})

        result = {
            "matched": match,
            "failed_conditions": failed_conditions,
            "evaluated_response": response if match else {},
        }

        logger.debug("Preview result: %s", result)
        return JsonResponse({"success": True, "result": result})

    except Exception as e:
        logger.exception("Preview logic error: %s", e)
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    
