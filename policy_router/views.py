import re
import httpx
import json
import csv
import io
import base64
from collections import defaultdict
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.urls import reverse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from .models import PolicyProxyRule, PolicyRequestLog
from .forms import PolicyProxyRuleForm
from django.views.decorators.csrf import csrf_exempt
from policy_router.auth import basic_auth_django_user
from django.contrib.auth import authenticate
from django.http import HttpResponse, JsonResponse
from django.utils.encoding import smart_str
from django.db import transaction

def _increment_rule_usage(rule: PolicyProxyRule):
    """Increment usage metrics for a rule."""
    rule.match_count = (rule.match_count or 0) + 1
    rule.last_matched_at = timezone.now()
    rule.save(update_fields=["match_count", "last_matched_at"])

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

def maybe_protected(view_func):
    if settings.ENABLE_WEB_AUTH:
        return login_required(view_func)
    return view_func

def maybe_basic_auth_protected(view_func):
    """Enforce HTTP Basic Auth on policy endpoints if enabled."""
    from functools import wraps

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not getattr(settings, "ENABLE_POLICY_AUTH", False):
            return view_func(request, *args, **kwargs)

        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if not auth_header or not auth_header.lower().startswith("basic "):
            response = HttpResponse("Unauthorized", status=401)
            response["WWW-Authenticate"] = 'Basic realm="Policy API"'
            return response

        try:
            encoded = auth_header.split(" ")[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":", 1)
        except Exception:
            return HttpResponse("Invalid authentication header", status=400)

        user = authenticate(username=username, password=password)
        if user is None:
            response = HttpResponse("Invalid credentials", status=401)
            response["WWW-Authenticate"] = 'Basic realm="Policy API"'
            return response

        request.user = user
        return view_func(request, *args, **kwargs)

    return _wrapped

def _log_request(rule, request, response=None, is_override=False, override_response=None):
    """Log inbound policy requests."""
    from .models import PolicyRequestLog

    client_ip = request.META.get("REMOTE_ADDR")
    host = request.META.get("HTTP_HOST", "")
    source_host = client_ip or host or None

    log_entry = PolicyRequestLog.objects.create(
        rule=rule,
        request_path=request.path,
        request_method=request.method,
        request_body=request.body.decode("utf-8", errors="ignore") if request.body else "",
        response_body=json.dumps(
            override_response if is_override else getattr(response, "text", ""),
            ensure_ascii=False,
        ),
        response_status=getattr(response, "status_code", 200),
        is_override=is_override,
        source_host=source_host,
    )


    return log_entry

@maybe_protected
@require_http_methods(["GET"])
def export_logs_txt(request):
    """
    Export PolicyRequestLog entries to a plain .log text file.
    Each line includes timestamp, rule, method, path, status, and source host.
    """
    response = HttpResponse(content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="policy_logs.log"'

    logs = PolicyRequestLog.objects.select_related("rule").order_by("-created_at")

    for log in logs:
        rule_name = log.rule.name if log.rule else "N/A"
        line = (
            f"[{log.created_at.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{log.request_method} {log.request_path} "
            f"({rule_name}) "
            f"status={log.response_status} "
            f"override={log.is_override} "
            f"source={log.source_host or 'unknown'}\n"
        )
        response.write(line)

    return response


# -----------------------------
# CSV EXPORT
# -----------------------------
@maybe_protected
def manage_rules_view(request):
    """Render page for managing CSV import/export."""
    return render(request, "policy_router/manage_rules.html")

@maybe_protected
@require_http_methods(["GET"])
def export_rules_csv(request):
    """Export all rules to CSV."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="policy_rules.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "name",
        "regex",
        "priority",
        "is_active",
        "protocols",
        "call_directions",
        "source_match",
        "service_target_url",
        "participant_target_url",
        "basic_auth_username",
        "basic_auth_password",
        "always_continue_service",
        "override_service_response",
        "always_continue_participant",
        "override_participant_response",
    ])

    for rule in PolicyProxyRule.objects.all().order_by("priority"):
        writer.writerow([
            smart_str(rule.name or ""),
            smart_str(rule.regex or ""),
            smart_str(rule.priority or ""),
            smart_str(rule.is_active),
            json.dumps(rule.protocols or []),
            json.dumps(rule.call_directions or []),
            smart_str(rule.source_match or ""),
            smart_str(rule.service_target_url or ""),
            smart_str(rule.participant_target_url or ""),
            smart_str(rule.basic_auth_username or ""),
            smart_str(rule.basic_auth_password or ""),
            smart_str(rule.always_continue_service),
            json.dumps(rule.override_service_response or {}),
            smart_str(rule.always_continue_participant),
            json.dumps(rule.override_participant_response or {}),
        ])

    return response


# -----------------------------
# CSV IMPORT
# -----------------------------
@csrf_exempt
@maybe_protected
@require_http_methods(["POST"])
def import_rules_csv(request):
    """
    Import or update rules from a CSV upload.
    Returns JSON if requested via AJAX, else redirects.
    """
    def json_response(data, status=200):
        return JsonResponse(data, status=status)

    file = request.FILES.get("file")
    if not file:
        msg = "No CSV file uploaded."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return json_response({"error": msg}, status=400)
        messages.error(request, msg)
        return redirect("policy_router:rule_list")

    try:
        decoded_file = file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded_file))
    except Exception as e:
        msg = f"Could not read CSV: {e}"
        logger.exception(msg)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return json_response({"error": msg}, status=400)
        messages.error(request, msg)
        return redirect("policy_router:rule_list")

    allow_update = True  # toggle later if you add checkbox
    created, updated, failed = 0, 0, 0

    with transaction.atomic():
        for i, row in enumerate(reader, start=1):
            name = row.get("name")
            regex = row.get("regex")
            if not name or not regex:
                failed += 1
                continue

            def parse_json(v, default):
                try:
                    return json.loads(v) if v else default
                except Exception:
                    return default

            try:
                protocols = parse_json(row.get("protocols"), [])
                call_dirs = parse_json(row.get("call_directions"), [])
                override_service = parse_json(row.get("override_service_response"), {})
                override_part = parse_json(row.get("override_participant_response"), {})

                defaults = {
                    "regex": regex,
                    "priority": int(row.get("priority", 0) or 0),
                    "is_active": str(row.get("is_active", "True")).lower() in ("true","1","yes"),
                    "protocols": protocols,
                    "call_directions": call_dirs,
                    "source_match": row.get("source_match") or None,
                    "service_target_url": row.get("service_target_url") or None,
                    "participant_target_url": row.get("participant_target_url") or None,
                    "basic_auth_username": row.get("basic_auth_username") or None,
                    "basic_auth_password": row.get("basic_auth_password") or None,
                    "always_continue_service": str(row.get("always_continue_service","False")).lower() in ("true","1","yes"),
                    "override_service_response": override_service,
                    "always_continue_participant": str(row.get("always_continue_participant","False")).lower() in ("true","1","yes"),
                    "override_participant_response": override_part,
                }

                obj, created_flag = PolicyProxyRule.objects.update_or_create(name=name, defaults=defaults)
                if created_flag:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                failed += 1
                logger.exception(f"Row {i} import failed: {e}")
                continue

    message = f"✅ Import complete — {created} created, {updated} updated"
    if failed:
        message += f", {failed} skipped."

    # --- AJAX response ---
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return json_response({"message": message})

    # --- Fallback for normal POST ---
    messages.success(request, message)
    return redirect("policy_router:rule_list")

# -----------------------------
# Rule Tester
# -----------------------------
@maybe_protected
@require_http_methods(["GET", "POST"])
def rule_tester(request):
    result = None
    matched_rule = None
    selected_type = "service"

    if request.method == "POST":
        selected_type = request.POST.get("policy_type", "service")
        local_alias = request.POST.get("local_alias")
        protocol = request.POST.get("protocol")
        call_direction = request.POST.get("call_direction")

        rules = PolicyProxyRule.objects.filter(is_active=True).order_by("priority", "-updated_at")

        for rule in rules:
            try:
                # Match alias
                if not re.search(rule.regex, local_alias or ""):
                    continue
                # Match protocol and call direction
                if rule.protocols and protocol not in rule.protocols:
                    continue
                if rule.call_directions and call_direction not in rule.call_directions:
                    continue

                matched_rule = rule

                # --- Simulated service/participant handling ---
                if selected_type == "service":
                    if rule.always_continue_service:
                        response_data = rule.override_service_response or {"status": "success", "action": "continue"}
                        result = {
                            "matched": True,
                            "type": "override",
                            "response": json.dumps(response_data),  # ✅ serialize JSON properly
                            "rule": rule,
                            "mode": "service",
                        }
                    elif rule.service_target_url:
                        result = {
                            "matched": True,
                            "type": "proxy",
                            "response": json.dumps({"info": f"Would proxy to {rule.service_target_url}"}),
                            "rule": rule,
                            "mode": "service",
                        }
                    else:
                        result = {
                            "matched": True,
                            "type": "none",
                            "response": json.dumps({"warning": "No target or override set"}),
                            "rule": rule,
                            "mode": "service",
                        }

                else:  # participant mode
                    if rule.always_continue_participant:
                        response_data = rule.override_participant_response or {"status": "success", "action": "continue"}
                        result = {
                            "matched": True,
                            "type": "override",
                            "response": json.dumps(response_data),  # ✅ serialize JSON properly
                            "rule": rule,
                            "mode": "participant",
                        }
                    elif rule.participant_target_url:
                        result = {
                            "matched": True,
                            "type": "proxy",
                            "response": json.dumps({"info": f"Would proxy to {rule.participant_target_url}"}),
                            "rule": rule,
                            "mode": "participant",
                        }
                    else:
                        result = {
                            "matched": True,
                            "type": "none",
                            "response": json.dumps({"warning": "No target or override set"}),
                            "rule": rule,
                            "mode": "participant",
                        }

                break
            except re.error:
                continue

        if not result:
            result = {"matched": False, "error": "No matching rule found"}

    return render(request, "policy_router/rule_tester.html", {
        "protocol_choices": PolicyProxyRule.PROTOCOL_CHOICES,
        "call_direction_choices": PolicyProxyRule.CALL_DIRECTION_CHOICES,
        "result": result,
        "matched_rule": matched_rule,
        "selected_type": selected_type,
    })

# -----------------------------
# Policy Views
# -----------------------------
@csrf_exempt
@maybe_basic_auth_protected
def proxy_service_policy(request):
    """Proxy for /policy/v1/service/configuration (always GET)."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    local_alias = request.GET.get("local_alias")
    req_protocol = request.GET.get("protocol")
    req_call_direction = request.GET.get("call_direction")

    rules = PolicyProxyRule.objects.filter(is_active=True).order_by("priority", "-updated_at")
    # Capture client origin
    client_ip = request.META.get("REMOTE_ADDR")
    client_host = request.META.get("HTTP_HOST", "").split(":")[0].lower() if request.META.get("HTTP_HOST") else None

    for rule in rules:
        try:
            if re.search(rule.regex, local_alias or ""):
                # Check protocol/call_direction match if specified
                if rule.protocols and req_protocol and req_protocol not in rule.protocols:
                    continue
                if rule.call_directions and req_call_direction and req_call_direction not in rule.call_directions:
                    continue
                
                # --- Track usage ---
                _increment_rule_usage(rule) 

                # --- Override check ---
                if rule.always_continue_service:
                    response_json = rule.override_service_response or {"status": "success", "action": "continue"}
                    _log_request(rule, request, None, is_override=True, override_response=response_json)
                    return JsonResponse(response_json)

                if rule.source_match:
                    src = rule.source_match.strip().lower()
                    if not (
                        client_ip == src
                        or client_host == src
                        or src in (client_ip or "")
                        or src in (client_host or "")
                    ):
                        continue  # skip rule, source doesn't match

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

@csrf_exempt
@maybe_basic_auth_protected
def proxy_participant_policy(request):
    """Proxy for /policy/v1/participant/properties (always GET)."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    local_alias = request.GET.get("local_alias")
    req_protocol = request.GET.get("protocol")
    req_call_direction = request.GET.get("call_direction")
    client_ip = request.META.get("REMOTE_ADDR")
    client_host = request.get_host().split(":")[0] if "HTTP_HOST" in request.META else None
    rules = PolicyProxyRule.objects.filter(is_active=True).order_by("priority", "-updated_at")

    for rule in rules:
        try:
            if re.search(rule.regex, local_alias or ""):
                # Check protocol/call_direction match if specified
                if rule.protocols and req_protocol and req_protocol not in rule.protocols:
                    continue
                if rule.call_directions and req_call_direction and req_call_direction not in rule.call_directions:
                    continue
                if rule.source_match:
                    src = rule.source_match.strip().lower()
                    if not (
                        client_ip == src
                        or client_host == src
                        or src in (client_ip or "")
                        or src in (client_host or "")
                    ):
                        continue  # skip rule, source doesn't match
                # --- Track usage ---
                _increment_rule_usage(rule)  

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
@maybe_protected
def rule_list(request):
    import re
    import random

    # --- Base queryset + filters ---
    rules = PolicyProxyRule.objects.all().order_by("priority", "id")

    protocols = request.GET.getlist("protocols")
    call_directions = request.GET.getlist("call_directions")
    source = request.GET.get("source_match")  # ✅ new filter

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

    if source:
        if source == "__any__":
            rules = rules.filter(Q(source_match__isnull=True) | Q(source_match__exact=""))
        else:
            rules = rules.filter(source_match__iexact=source)

    # --- Collect distinct source values for dropdown ---
    distinct_sources = (
        PolicyProxyRule.objects.exclude(source_match__isnull=True)
        .exclude(source_match__exact="")
        .values_list("source_match", flat=True)
        .distinct()
    )

    # --- Duplicate detection (unchanged) ---
    base_samples = [
        "room-1", "room-12", "room-123", "room-9999",
        "vmr-01", "vmr-999", "test", "room-", "conference-01",
        "chair-1", "defence-99", "guest-1234",
    ]
    for i in range(10):
        base_samples.append(f"room-{random.randint(0,9999)}")
        base_samples.append(f"vmr-{random.randint(0,9999)}")

    duplicate_ids = set()
    duplicate_map = {}

    rules = list(rules)

    for i, r1 in enumerate(rules):
        try:
            regex1 = re.compile(r1.regex)
        except re.error:
            continue

        for r2 in rules[i + 1:]:
            try:
                regex2 = re.compile(r2.regex)
            except re.error:
                continue

            if r1.regex == r2.regex:
                duplicate_ids.update([r1.id, r2.id])
                duplicate_map.setdefault(r1.id, set()).add(r2.name)
                duplicate_map.setdefault(r2.id, set()).add(r1.name)
                continue

            for sample in base_samples:
                if regex1.search(sample) and regex2.search(sample):
                    duplicate_ids.update([r1.id, r2.id])
                    duplicate_map.setdefault(r1.id, set()).add(r2.name)
                    duplicate_map.setdefault(r2.id, set()).add(r1.name)
                    break

    return render(request, "policy_router/rule_list.html", {
        "rules": rules,
        "protocol_choices": PolicyProxyRule.PROTOCOL_CHOICES,
        "call_direction_choices": PolicyProxyRule.CALL_DIRECTION_CHOICES,
        "distinct_sources": distinct_sources,  # ✅ added
        "filters": {
            "protocols": protocols,
            "call_directions": call_directions,
            "source_match": source,  # ✅ added
        },
        "duplicate_ids": duplicate_ids,
        "duplicate_map": duplicate_map,
    })



@maybe_protected
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

@maybe_protected
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

@maybe_protected
def rule_delete(request, pk):
    rule = get_object_or_404(PolicyProxyRule, pk=pk)
    if request.method == "POST":
        rule.delete()
        messages.success(request, "Deleted")
        return redirect(reverse("policy_router:rule_list"))
    return render(request, "policy_router/rule_confirm_delete.html", {"rule": rule})

@maybe_protected
def rule_duplicate(request, pk):
    """Duplicate an existing rule."""
    original = get_object_or_404(PolicyProxyRule, pk=pk)
    clone = PolicyProxyRule.objects.get(pk=pk)

    # Detach and modify
    clone.pk = None  # ensures a new object is created
    clone.name = f"Copy of {original.name}"
    clone.priority = original.priority + 1  # optional: shift priority slightly
    clone.is_active = False  # optional: prevent accidental activation
    clone.save()

    messages.success(request, f'Rule "{original.name}" duplicated as "{clone.name}".')
    return redirect("policy_router:rule_edit", pk=clone.pk)

@maybe_protected
def rule_move_up(request, pk):
    rule = get_object_or_404(PolicyProxyRule, pk=pk)
    prev_rule = PolicyProxyRule.objects.filter(priority__lt=rule.priority).order_by("-priority").first()
    if prev_rule:
        rule.priority, prev_rule.priority = prev_rule.priority, rule.priority
        rule.save()
        prev_rule.save()
    return redirect("policy_router:rule_list")

@maybe_protected
def rule_move_down(request, pk):
    rule = get_object_or_404(PolicyProxyRule, pk=pk)
    next_rule = PolicyProxyRule.objects.filter(priority__gt=rule.priority).order_by("priority").first()
    if next_rule:
        rule.priority, next_rule.priority = next_rule.priority, rule.priority
        rule.save()
        next_rule.save()
    return redirect("policy_router:rule_list")

@maybe_protected
def resequence_rules_view(request):
    rules = PolicyProxyRule.objects.all().order_by("priority", "id")
    for index, rule in enumerate(rules, start=1):
        rule.priority = index
        rule.save(update_fields=["priority"])
    messages.success(request, "Rules resequenced successfully.")
    return redirect("policy_router:rule_list")

@maybe_protected
@require_POST
def reorder_rules(request):
    """Update rule priorities based on drag-drop order."""
    try:
        data = json.loads(request.body)
        new_order = data.get("order", [])
        for i, rule_id in enumerate(new_order, start=1):
            PolicyProxyRule.objects.filter(id=rule_id).update(priority=i)
        return JsonResponse({"status": "ok", "message": "Rules reordered"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
    
@require_POST
@maybe_protected
@csrf_exempt
def rule_reorder(request):
    """
    Receive an ordered list of rule IDs and resequence their priorities accordingly.
    """
    try:
        data = json.loads(request.body)
        order = data.get("order", [])
        if not order or not isinstance(order, list):
            return JsonResponse({"status": "error", "message": "Invalid order payload"}, status=400)

        with transaction.atomic():
            for index, rule_id in enumerate(order):
                PolicyProxyRule.objects.filter(id=rule_id).update(priority=index + 1)

        return JsonResponse({"status": "ok", "refresh": True})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
@maybe_protected
def rule_check_duplicates(request):
    """Scan all active rules for overlapping regex patterns (semantic check)."""
    import re
    import random

    rules = list(PolicyProxyRule.objects.filter(is_active=True))
    duplicates = []

    # Common alias shapes likely to occur in Pexip
    base_samples = [
        "room-1", "room-12", "room-123", "room-9999",
        "vmr-01", "vmr-999", "test", "room-", "conference-01",
        "chair-1", "defence-99", "guest-1234",
    ]
    # Add random variations for diversity
    for i in range(20):
        base_samples.append(f"room-{random.randint(0,9999)}")
        base_samples.append(f"vmr-{random.randint(0,9999)}")

    for i, r1 in enumerate(rules):
        try:
            regex1 = re.compile(r1.regex)
        except re.error:
            continue

        for r2 in rules[i + 1:]:
            try:
                regex2 = re.compile(r2.regex)
            except re.error:
                continue

            # Skip exact duplicates
            if r1.regex == r2.regex:
                duplicates.append((r1, r2, "Exact duplicate"))
                continue

            # Check semantic overlap — any string matching both
            for sample in base_samples:
                if regex1.search(sample) and regex2.search(sample):
                    duplicates.append((r1, r2, f"Both match '{sample}'"))
                    break

    return render(request, "policy_router/rule_duplicates.html", {
        "duplicates": duplicates,
    })

# -----------------------------
# Logs
# -----------------------------
@maybe_protected
def log_list(request):
    logs = PolicyRequestLog.objects.select_related("rule").order_by("-created_at")

    local_alias = request.GET.get("local_alias")
    rule_id = request.GET.get("rule")
    start_datetime = request.GET.get("start_datetime")
    end_datetime = request.GET.get("end_datetime")
    source_host = request.GET.get("source_host")  # 👈 new filter

    protocols = request.GET.getlist("protocols")
    call_directions = request.GET.getlist("call_directions")

    # --- Apply filters ---
    if local_alias:
        logs = logs.filter(request_path__icontains=local_alias)

    if rule_id:
        logs = logs.filter(rule_id=rule_id)

    if protocols:
        logs = logs.filter(protocol__in=protocols)

    if call_directions:
        logs = logs.filter(call_direction__in=call_directions)

    if source_host:
        logs = logs.filter(source_host__icontains=source_host)

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

    # --- Distinct list of sources for dropdown ---
    distinct_sources = (
        PolicyRequestLog.objects.exclude(source_host__isnull=True)
        .exclude(source_host__exact="")
        .values_list("source_host", flat=True)
        .distinct()
        .order_by("source_host")
    )

    paginator = Paginator(logs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "policy_router/log_list.html", {
        "page_obj": page_obj,
        "rules": PolicyProxyRule.objects.all(),
        "protocol_choices": PolicyProxyRule.PROTOCOL_CHOICES,
        "call_direction_choices": PolicyProxyRule.CALL_DIRECTION_CHOICES,
        "distinct_sources": distinct_sources,  # 👈 added
        "filters": {
            "local_alias": local_alias or "",
            "rule": rule_id or "",
            "protocols": protocols,
            "call_directions": call_directions,
            "start_datetime": start_datetime or "",
            "end_datetime": end_datetime or "",
            "source_host": source_host or "",  # 👈 added
        }
    })

