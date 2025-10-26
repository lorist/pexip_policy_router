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

    # Ensure logic objects exist
    participant_logic, _ = PolicyLogic.objects.get_or_create(
        rule=rule,
        rule_type="participant",
        defaults={"enabled": True, "conditions": {}, "response": {}},
    )
    service_logic, _ = PolicyLogic.objects.get_or_create(
        rule=rule,
        rule_type="service",
        defaults={"enabled": True, "conditions": {}, "response": {}},
    )

    if request.method == "GET":
        logger.debug(
            "Logic editor opened for rule %s (participant_id=%s, service_id=%s)",
            rule.id,
            participant_logic.id,
            service_logic.id,
        )

    elif request.method == "POST":
        logger.info("🧠 Saving advanced logic for rule %s", rule.id)
        updates = []

        for logic in (participant_logic, service_logic):
            ltype = logic.rule_type
            try:
                # Capture old state for diff
                old_state = {
                    "enabled": logic.enabled,
                    "conditions": logic.conditions,
                    "response": logic.response,
                }

                cond_json = request.POST.get(f"{ltype}_conditions", "{}")
                resp_json = request.POST.get(f"{ltype}_response", "{}")
                logic.conditions = json.loads(cond_json)
                logic.response = json.loads(resp_json)
                logic.enabled = bool(request.POST.get(f"{ltype}_enabled"))
                logic.save()

                # Diff detection
                diffs = []
                for k in ["enabled", "conditions", "response"]:
                    if logic.__dict__.get(k) != old_state.get(k):
                        diffs.append(k)

                updates.append(f"{ltype}: updated {', '.join(diffs) or 'no changes'}")

            except json.JSONDecodeError as e:
                logger.warning(
                    "Invalid JSON for %s logic in rule %s: %s",
                    ltype,
                    rule.id,
                    e,
                )
            except Exception as e:
                logger.exception(
                    "Unexpected error saving %s logic for rule %s: %s",
                    ltype,
                    rule.id,
                    e,
                )

        if updates:
            logger.info("Rule %s logic updates → %s", rule.id, "; ".join(updates))
        else:
            logger.debug("Rule %s logic save completed: no changes detected", rule.id)

    context = {
        "rule": rule,
        "participant_logic": participant_logic,
        "service_logic": service_logic,
    }
    return render(request, "policy_engine/logic_editor.html", context)
