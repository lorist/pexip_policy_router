import re
import httpx
import json
from datetime import datetime
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from .models import PolicyProxyRule, PolicyRequestLog
from .forms import PolicyProxyRuleForm


# -----------------------------
# Helpers
# -----------------------------
def _build_safe_headers(request):
    """Strip hop-by-hop headers that break proxying."""
    return {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in {"host", "connection", "content-length", "accept-encoding"}
    }


def _log_request(rule, request, response=None, is_override=False, override_response=None):
    """Save request/response info to DB."""
    PolicyRequestLog.objects.create(
        rule=rule,
        request_method=request.method,
        request_path=request.get_full_path(),
        request_body=(request.body.decode("utf-8", errors="ignore") if request.body else None),
        response_status=(response.status_code if response else 200),
        response_body=(
            response.text
            if response
            else json.dumps(override_response or {"status": "success", "action": "continue"})
        ),
        is_override=is_override,
        call_direction=request.GET.get("call_direction"),
        protocol=request.GET.get("protocol"),
    )


# -----------------------------
# Proxy Views
# -----------------------------
def proxy_service_policy(request):
    """Proxy for /policy/v1/service/configuration (always GET)."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    local_alias = request.GET.get("local_alias")
    req_protocol = request.GET.get("protocol")
    req_call_direction = request.GET.get("call_direction")

    rules = PolicyProxyRule.objects.filter(is_active=True).order_by("priority", "-updated_at")

    for rule in rules:
        try:
            if re.search(rule.regex, local_alias or ""):
                # Check protocol/call_direction match if specified
                if rule.protocols and req_protocol and req_protocol not in rule.protocols:
                    continue
                if rule.call_directions and req_call_direction and req_call_direction not in rule.call_directions:
                    continue

                # --- Override check ---
                if rule.always_continue_service:
                    response_json = rule.override_service_response or {"status": "success", "action": "continue"}
                    _log_request(rule, request, None, is_override=True, override_response=response_json)
                    return JsonResponse(response_json)

                if rule.service_target_url:
                    upstream = rule.service_target_url.rstrip("/")
                    try:
                        resp = httpx.get(
                            upstream + request.path,
                            params=request.GET,
                            headers=_build_safe_headers(request),
                            auth=(
                                (rule.basic_auth_username, rule.basic_auth_password)
                                if rule.basic_auth_username and rule.basic_auth_password
                                else None
                            ),
                            timeout=10.0,
                        )
                        _log_request(rule, request, resp)
                        try:
                            return JsonResponse(resp.json(), status=resp.status_code)
                        except ValueError:
                            return JsonResponse({"raw": resp.text}, status=resp.status_code)
                    except httpx.RequestError as e:
                        return JsonResponse({"error": f"Upstream request failed: {e}"}, status=502)
        except re.error:
            continue

    return JsonResponse({"error": "No matching rule"}, status=404)



def proxy_participant_policy(request):
    """Proxy for /policy/v1/participant/properties (always GET)."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    local_alias = request.GET.get("local_alias")
    req_protocol = request.GET.get("protocol")
    req_call_direction = request.GET.get("call_direction")

    rules = PolicyProxyRule.objects.filter(is_active=True).order_by("priority", "-updated_at")

    for rule in rules:
        try:
            if re.search(rule.regex, local_alias or ""):
                # Check protocol/call_direction match if specified
                if rule.protocols and req_protocol and req_protocol not in rule.protocols:
                    continue
                if rule.call_directions and req_call_direction and req_call_direction not in rule.call_directions:
                    continue

                # --- Override check ---
                if rule.always_continue_participant:
                    response_json = rule.override_participant_response or {"status": "success", "action": "continue"}
                    _log_request(rule, request, None, is_override=True, override_response=response_json)
                    return JsonResponse(response_json)

                if rule.participant_target_url:
                    upstream = rule.participant_target_url.rstrip("/")
                    try:
                        resp = httpx.get(
                            upstream + request.path,
                            params=request.GET,
                            headers=_build_safe_headers(request),
                            auth=(
                                (rule.basic_auth_username, rule.basic_auth_password)
                                if rule.basic_auth_username and rule.basic_auth_password
                                else None
                            ),
                            timeout=10.0,
                        )
                        _log_request(rule, request, resp)

                        try:
                            return JsonResponse(resp.json(), status=resp.status_code)
                        except ValueError:
                            return JsonResponse({"raw": resp.text}, status=resp.status_code)
                    except httpx.RequestError as e:
                        return JsonResponse({"error": f"Upstream request failed: {e}"}, status=502)
        except re.error:
            continue

    return JsonResponse({"error": "No matching rule"}, status=404)



# -----------------------------
# Rules Management
# -----------------------------
def rule_list(request):
    rules = PolicyProxyRule.objects.all().order_by("priority", "-updated_at")

    protocols = request.GET.getlist("protocols")
    call_directions = request.GET.getlist("call_directions")

    if protocols:
        q = Q()
        for proto in protocols:
            q |= Q(protocols__icontains=proto)
        rules = rules.filter(q)

    if call_directions:
        q = Q()
        for cd in call_directions:
            q |= Q(call_directions__icontains=cd)
        rules = rules.filter(q)

    return render(request, "policy_router/rule_list.html", {
        "rules": rules,
        "protocol_choices": PolicyProxyRule.PROTOCOL_CHOICES,
        "call_direction_choices": PolicyProxyRule.CALL_DIRECTION_CHOICES,
        "filters": {
            "protocols": protocols,
            "call_directions": call_directions,
        }
    })



def rule_create(request):
    if request.method == "POST":
        form = PolicyProxyRuleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Created")
            return redirect(reverse("policy_router:rule_list"))
    else:
        form = PolicyProxyRuleForm()
    return render(request, "policy_router/rule_form.html", {"form": form})


def rule_edit(request, pk):
    rule = get_object_or_404(PolicyProxyRule, pk=pk)
    if request.method == "POST":
        form = PolicyProxyRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, "Updated")
            return redirect(reverse("policy_router:rule_list"))
    else:
        form = PolicyProxyRuleForm(instance=rule)
    return render(request, "policy_router/rule_form.html", {"form": form})


def rule_delete(request, pk):
    rule = get_object_or_404(PolicyProxyRule, pk=pk)
    if request.method == "POST":
        rule.delete()
        messages.success(request, "Deleted")
        return redirect(reverse("policy_router:rule_list"))
    return render(request, "policy_router/rule_confirm_delete.html", {"rule": rule})


# -----------------------------
# Logs
# -----------------------------
def log_list(request):
    logs = PolicyRequestLog.objects.select_related("rule").order_by("-created_at")

    local_alias = request.GET.get("local_alias")
    rule_id = request.GET.get("rule")
    start_datetime = request.GET.get("start_datetime")
    end_datetime = request.GET.get("end_datetime")

    protocols = request.GET.getlist("protocols")
    call_directions = request.GET.getlist("call_directions")

    if local_alias:
        logs = logs.filter(request_path__icontains=local_alias)
    if rule_id:
        logs = logs.filter(rule_id=rule_id)
    if protocols:
        logs = logs.filter(protocol__in=protocols)
    if call_directions:
        logs = logs.filter(call_direction__in=call_directions)
    if start_datetime:
        try:
            start_dt = datetime.fromisoformat(start_datetime)
            logs = logs.filter(created_at__gte=start_dt)
        except ValueError:
            pass
    if end_datetime:
        try:
            end_dt = datetime.fromisoformat(end_datetime)
            logs = logs.filter(created_at__lte=end_dt)
        except ValueError:
            pass

    paginator = Paginator(logs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "policy_router/log_list.html", {
        "page_obj": page_obj,
        "rules": PolicyProxyRule.objects.all(),
        "protocol_choices": PolicyProxyRule.PROTOCOL_CHOICES,
        "call_direction_choices": PolicyProxyRule.CALL_DIRECTION_CHOICES,
        "filters": {
            "local_alias": local_alias or "",
            "rule": rule_id or "",
            "protocols": protocols,
            "call_directions": call_directions,
            "start_datetime": start_datetime or "",
            "end_datetime": end_datetime or "",
        }
    })
