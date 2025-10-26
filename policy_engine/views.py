import json, logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponseBadRequest
from django.urls import reverse

from policy_router.models import PolicyProxyRule
from .models import PolicyLogic
from .forms import PolicyLogicForm
from .utils import evaluate_conditions

logger = logging.getLogger(__name__)

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
def logic_editor(request, rule_id: int):
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)

    participant_logic, _ = PolicyLogic.objects.get_or_create(
        rule=rule, rule_type=PolicyLogic.RuleType.PARTICIPANT, defaults={}
    )
    service_logic, _ = PolicyLogic.objects.get_or_create(
        rule=rule, rule_type=PolicyLogic.RuleType.SERVICE, defaults={}
    )

    active_tab = request.POST.get("active_tab", request.GET.get("tab", "participant"))

    if request.method == "POST":
        target = participant_logic if active_tab == "participant" else service_logic
        form = PolicyLogicForm(request.POST, instance=target)
        if form.is_valid():
            form.save()
            messages.success(request, f"{active_tab.capitalize()} logic saved.")
            return redirect(
                reverse("policy_engine:logic_editor", args=[rule.id]) + f"?tab={active_tab}"
            )
        else:
            messages.error(request, "Please fix the errors below.")
            # keep other form bound to its instance (not posted)
            other = service_logic if active_tab == "participant" else participant_logic
            other_form = PolicyLogicForm(instance=other)
            context = {
                "rule": rule,
                "participant_form": form if active_tab == "participant" else other_form,
                "service_form": form if active_tab == "service" else other_form,
                "active_tab": active_tab,
            }
            return render(request, "policy_engine/logic_editor.html", context)

    participant_form = PolicyLogicForm(instance=participant_logic)
    service_form = PolicyLogicForm(instance=service_logic)

    context = {
        "rule": rule,
        "participant_form": participant_form,
        "service_form": service_form,
        "active_tab": active_tab,
    }
    return render(request, "policy_engine/logic_editor.html", context)


@require_http_methods(["POST"])
def preview_logic(request, rule_id: int):
    """
    POST to preview endpoint with:
      - tab: "participant" | "service"
      - conditions_text: JSON (string)
      - response_text: JSON (string)
      - sample_call_info: JSON (string)
      - enabled: "on" | "" (optional)
    Returns a JSON payload describing whether the rule matches and what would be returned.
    """
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)
    tab = request.POST.get("tab", "participant")
    enabled = request.POST.get("enabled") == "on"

    try:
        conditions = json.loads(request.POST.get("conditions_text") or "{}")
        if not isinstance(conditions, dict):
            raise ValueError("conditions must be a JSON object")
    except Exception as e:
        return HttpResponseBadRequest(f"Invalid conditions JSON: {e}")

    try:
        response = json.loads(request.POST.get("response_text") or "{}")
        if not isinstance(response, dict):
            raise ValueError("response must be a JSON object")
    except Exception as e:
        return HttpResponseBadRequest(f"Invalid response JSON: {e}")

    try:
        sample_call_info = json.loads(request.POST.get("sample_call_info") or "{}")
        if not isinstance(sample_call_info, dict):
            raise ValueError("sample_call_info must be a JSON object")
    except Exception as e:
        return HttpResponseBadRequest(f"Invalid sample_call_info JSON: {e}")

    if not enabled:
        return JsonResponse(
            {
                "enabled": False,
                "matched": False,
                "returned": {},
                "message": "Logic disabled — no response would be returned.",
            }
        )

    matched = evaluate_conditions(sample_call_info, conditions)
    returned = response if matched else {}
    message = "Conditions matched." if matched else "Conditions did not match."

    return JsonResponse(
        {
            "enabled": True,
            "matched": matched,
            "returned": returned,
            "message": message,
            "rule": rule.id,
            "tab": tab,
        }
    )
