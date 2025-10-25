import json
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from policy_router.models import PolicyProxyRule
from django.core.paginator import Paginator
from .models import PolicyLogic, PolicyDecisionLog
from policy_router.views import maybe_protected
import logging

logger = logging.getLogger(__name__)

@require_http_methods(["GET", "POST"])
def logic_editor(request, rule_id):
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)
    participant_logic, _ = PolicyLogic.objects.get_or_create(rule=rule, rule_type=PolicyLogic.PARTICIPANT)
    service_logic, _ = PolicyLogic.objects.get_or_create(rule=rule, rule_type=PolicyLogic.SERVICE)

    if request.method == 'POST':
        errors = False
        for key, instance in (("participant", participant_logic), ("service", service_logic)):
            instance.enabled = request.POST.get(f"{key}_enabled") == 'on'
            instance.description = request.POST.get(f"{key}_description", "")

            try:
                instance.conditions = json.loads(request.POST.get(f"{key}_conditions", '{}'))
            except json.JSONDecodeError as e:
                messages.error(request, f"{key.title()} conditions JSON invalid: {e}")
                errors = True

            try:
                instance.response = json.loads(request.POST.get(f"{key}_response", '{}'))
            except json.JSONDecodeError as e:
                messages.error(request, f"{key.title()} response JSON invalid: {e}")
                errors = True

            if not errors:
                instance.save()

        if not errors:
            messages.success(request, "Advanced logic saved.")
            return redirect('policy_router:rule_list')

    return render(request, 'policy_engine/logic_editor.html', {
        'rule': rule,
        'participant': participant_logic,
        'service': service_logic,
    })

@maybe_protected
@require_http_methods(["GET"])
def logic_decision_log_list(request, rule_id):
    """Show all decision logs for a specific rule."""
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)
    logs = PolicyDecisionLog.objects.filter(rule_id=rule_id).order_by("-decided_at")

    paginator = Paginator(logs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    logger.debug(f"🪵 Found {logs.count()} decision logs for rule {rule_id}")

    return render(
        request,
        "policy_engine/logic_decision_logs.html",
        {
            "rule": rule,
            "logs": page_obj,
            "page_obj": page_obj,  # pagination controls
        },
    )

@maybe_protected
def logic_overview(request):
    """Show all advanced logic rules across all PolicyProxyRules."""
    logics = (
        PolicyLogic.objects
        .select_related("rule")
        .order_by("rule__priority", "rule__name", "rule_type")
    )

    context = {
        "logics": logics,
    }
    return render(request, "policy_engine/logic_overview.html", context)