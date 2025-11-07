import re
import httpx
import json
import csv
import io
import base64
import logging
from collections import defaultdict
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST, require_GET
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
from policy_engine.models import PolicyLogic, IdentityAttribute, IdentityValue
from policy_engine.utils import evaluate_conditions, apply_template, normalize_policy_response
from django.contrib.auth import authenticate
from django.http import HttpResponse, JsonResponse
from django.utils.encoding import smart_str
from django.db import transaction
from policy_router.engine import evaluate_policy


# Setup console logging
logger = logging.getLogger(__name__)

def finalize_response(response_json, call_info, status=200):
    """
    Apply Jinja templating + policy response normalization,
    and return a proper JsonResponse.
    """
    response_json = apply_template(response_json, call_info)
    response_json = normalize_policy_response(response_json)
    return JsonResponse(response_json, status=status)

def _increment_rule_usage(rule: PolicyProxyRule):
    """Increment usage metrics for a rule."""
    rule.match_count = (rule.match_count or 0) + 1
    rule.last_matched_at = timezone.now()
    rule.save(update_fields=["match_count", "last_matched_at"])

def _get_client_ip(request):
    if (client_ip := request.headers.get("X-Client-Ip")): return client_ip # Return Azure X header as client IP, if exists
    if (client_ip := request.META.get("HTTP_X_FORWARDED_FOR")): return client_ip # Return META HTTP_X_FORWARDED_FOR  as client IP, if exists
    if (client_ip := request.META.get("REMOTE_ADDR")): return client_ip # Return standard META REMOTE_ADDR, if exists
    return None # Default to None if no matches above

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

# def _log_request(
#     rule,
#     request,
#     response=None,
#     is_override=False,
#     override_response=None,
#     matched_logic=False,
#     logic_response=None,
# ):
def _log_request(
    rule,
    request,
    upstream_response=None,
    matched_logic=False,
    logic_response=None,
    is_override=False,
    override_response=None,
):
    """
    Single unified logging function — ensures we always store the *rendered* policy response.
    """
    try:
        # Normalize call info for consistent templating
        call_info = {k: v[0] if isinstance(v, list) else v for k, v in dict(request.GET).items()}

        # Render logic response if provided
        rendered_logic = None
        if logic_response:
            rendered_logic = apply_template(logic_response, call_info)
            rendered_logic = normalize_policy_response(rendered_logic)

        # Render override response if applicable
        rendered_override = None
        if override_response:
            rendered_override = apply_template(override_response, call_info)
            rendered_override = normalize_policy_response(rendered_override)

        # Determine what response to store
        if matched_logic and rendered_logic is not None:
            final_body = rendered_logic
            final_status = 200
        elif is_override and rendered_override is not None:
            final_body = rendered_override
            final_status = 200
        elif upstream_response is not None:
            final_status = upstream_response.status_code
            try:
                final_body = upstream_response.json()
            except Exception:
                final_body = {"raw": upstream_response.text}
        else:
            final_status = 200
            final_body = None

        PolicyRequestLog.objects.create(
            rule=rule,
            request_method=request.method,
            request_path=request.path,
            request_params=dict(request.GET),
            response_status=final_status,
            response_body=final_body,
            source_host=_get_client_ip(request) or request.get_host(),
            matched_logic=matched_logic,
            is_override=is_override,
        )

    except Exception:
        logger.exception(f"Logging failed for rule {rule.id}: {rule.name}")

def index(request):
    if request.user.is_authenticated:
        return redirect("policy_router:rule_list")
    return render(request, "policy_router/index.html")

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

        # Advanced logic fields
        "participant_logic_enabled",
        "participant_logic_conditions",
        "participant_logic_response",
        "service_logic_enabled",
        "service_logic_conditions",
        "service_logic_response",
        "idp_attributes"
    ])


    for rule in PolicyProxyRule.objects.all().order_by("priority"):
        # Fetch logic objects (may not exist)
        p_logic = PolicyLogic.objects.filter(rule=rule, rule_type="participant").first()
        s_logic = PolicyLogic.objects.filter(rule=rule, rule_type="service").first()

        writer.writerow([
            smart_str(rule.name or ""),
            smart_str(rule.regex or ""),
            smart_str(rule.priority or ""),
            smart_str(rule.is_active),
            json.dumps(rule.protocols or [], ensure_ascii=False),
            json.dumps(rule.call_directions or [], ensure_ascii=False),
            smart_str(rule.source_match or ""),
            smart_str(rule.service_target_url or ""),
            smart_str(rule.participant_target_url or ""),
            smart_str(rule.basic_auth_username or ""),
            smart_str(rule.basic_auth_password or ""),
            smart_str(rule.always_continue_service),
            json.dumps(rule.override_service_response or {}, ensure_ascii=False),
            smart_str(rule.always_continue_participant),
            json.dumps(rule.override_participant_response or {}, ensure_ascii=False),

            # Advanced logic export
            smart_str(p_logic.enabled if p_logic else ""),
            json.dumps(p_logic.conditions if p_logic else {}, ensure_ascii=False),
            json.dumps(p_logic.response if p_logic else {}, ensure_ascii=False),
            smart_str(s_logic.enabled if s_logic else ""),
            json.dumps(s_logic.conditions if s_logic else {}, ensure_ascii=False),
            json.dumps(s_logic.response if s_logic else {}, ensure_ascii=False),
            json.dumps(list(IdentityAttribute.objects.values_list("name", flat=True)), ensure_ascii=False)
        ])


    return response

# -----------------------------
# CSV IMPORT
# -----------------------------
from policy_engine.models import IdentityAttribute

def ensure_idp_attrs_exist(conditions):
    """
    Scan conditions JSON tree and create IdentityAttribute entries
    for any field like idp_attributes.<name>
    """
    if not isinstance(conditions, dict):
        return

    def walk(node):
        if isinstance(node, dict):
            # direct simple rule case
            field = node.get("field")
            if isinstance(field, str) and field.startswith("idp_attributes."):
                attr = field.split(".", 1)[1]
                IdentityAttribute.objects.get_or_create(name=attr)

            # nested groups
            for value in node.values():
                walk(value)

        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(conditions)

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
                # advanced logic fields
                p_logic_enabled_raw = row.get("participant_logic_enabled", "").strip()
                p_logic_enabled = p_logic_enabled_raw.lower() in ("true","1","yes")

                p_logic_conditions_raw = row.get("participant_logic_conditions", "").strip()
                p_logic_conditions = parse_json(p_logic_conditions_raw, {}) if p_logic_conditions_raw else {}

                p_logic_response_raw = row.get("participant_logic_response", "").strip()
                p_logic_response = parse_json(p_logic_response_raw, {}) if p_logic_response_raw else {}
                ensure_idp_attrs_exist(p_logic_conditions)

                s_logic_enabled_raw = row.get("service_logic_enabled", "").strip()
                s_logic_enabled = s_logic_enabled_raw.lower() in ("true","1","yes")

                s_logic_conditions_raw = row.get("service_logic_conditions", "").strip()
                s_logic_conditions = parse_json(s_logic_conditions_raw, {}) if s_logic_conditions_raw else {}

                s_logic_response_raw = row.get("service_logic_response", "").strip()
                s_logic_response = parse_json(s_logic_response_raw, {}) if s_logic_response_raw else {}
                ensure_idp_attrs_exist(s_logic_conditions)
                # Load idp_attributes list from CSV
                idp_attrs_raw = row.get("idp_attributes", "").strip()
                idp_attrs = parse_json(idp_attrs_raw, [])
                if isinstance(idp_attrs, list):
                   for attr in idp_attrs:
                       attr = str(attr).strip()
                       if attr:
                           IdentityAttribute.objects.get_or_create(name=attr)
                           
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

                # ------------------------------------------------
                # Restore Participant Logic (only if provided)
                # ------------------------------------------------
                if p_logic_enabled or p_logic_conditions or p_logic_response:
                    PolicyLogic.objects.update_or_create(
                        rule=obj,
                        rule_type="participant",
                        defaults={
                            "enabled": p_logic_enabled,
                            "conditions": p_logic_conditions,
                            "response": p_logic_response,
                        }
                    )

                # ------------------------------------------------
                # Restore Service Logic (only if provided)
                # ------------------------------------------------
                if s_logic_enabled or s_logic_conditions or s_logic_response:
                    PolicyLogic.objects.update_or_create(
                        rule=obj,
                        rule_type="service",
                        defaults={
                            "enabled": s_logic_enabled,
                            "conditions": s_logic_conditions,
                            "response": s_logic_response,
                        }
                    )

                # ------------------------------------------------
                # ENABLE ADVANCED LOGIC MODE on the rule if logic exists
                # ------------------------------------------------
                if (p_logic_enabled or p_logic_conditions or p_logic_response or
                    s_logic_enabled or s_logic_conditions or s_logic_response):
                    if not obj.advanced_logic_enabled:
                        obj.advanced_logic_enabled = True
                        obj.save(update_fields=["advanced_logic_enabled"])

                # ------------------------------------------------
                # Update counters AFTER rule + logic save
                # ------------------------------------------------
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
    logger.info("Received a service/configuration request")

    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    # Normalize outbound Pexip response
    def _normalize_service_response(data):
        if not isinstance(data, dict):
            return {"status": "success", "action": "continue", "result": {}}

        has_envelope = ("status" in data) or ("action" in data) or ("result" in data)
        if has_envelope:
            return {
                "status": data.get("status", "success"),
                "action": data.get("action", "continue"),
                "result": (data.get("result") if isinstance(data.get("result"), dict) else {})
            }

        return {"status": "success", "action": "continue", "result": data}

    # Build call_info (matching only)
    raw_params = dict(request.GET)
    call_info = {k: (v[0] if isinstance(v, list) else v) for k, v in raw_params.items()}

    idp_attrs = {}
    for k, v in list(call_info.items()):
        if k.startswith("idp_attribute_"):
            idp_attrs[k.replace("idp_attribute_", "")] = v
            del call_info[k]

    if idp_attrs:
        call_info["idp_attributes"] = idp_attrs

    # Restore cached identity attributes (the missing link!)
    subject = (
        call_info.get("idp_uuid")
        or call_info.get("remote_alias")
    )

    if subject:
        cached = IdentityValue.objects.filter(subject=subject).first()
        if cached and cached.attrs:
            call_info.setdefault("idp_attributes", {})
            call_info["idp_attributes"].update(cached.attrs)


    # Fallback identity name
    call_info.setdefault("idp_attributes", {})
    call_info["idp_attributes"].setdefault(
        "displayname",
        call_info.get("remote_display_name") or call_info.get("local_alias") or ""
    )
    call_info["idp_attributes"].setdefault("title", "")
    local_alias = call_info.get("local_alias")
    req_protocol = call_info.get("protocol")
    req_call_direction = call_info.get("call_direction")
    client_ip = _get_client_ip(request)
    client_host = request.META.get("HTTP_HOST", "").split(":")[0].lower() if request.META.get("HTTP_HOST") else None

    rules = PolicyProxyRule.objects.filter(is_active=True).order_by("priority", "-updated_at")

    for rule in rules:
        try:
            if not re.search(rule.regex, local_alias or ""):
                continue
            if rule.protocols and req_protocol and req_protocol not in rule.protocols:
                continue
            if rule.call_directions and req_call_direction and req_call_direction not in rule.call_directions:
                continue
            if rule.source_match:
                src = rule.source_match.strip().lower()
                if client_ip != src and client_host != src and src not in (client_ip or "") and src not in (client_host or ""):
                    continue

            _increment_rule_usage(rule)

            try:
                service_logic = PolicyLogic.objects.get(rule=rule, rule_type="service", enabled=True)
                match = evaluate_conditions(service_logic.conditions, call_info)
                if match["matched"]:

                    # Ensure fallback displayname for Jinja
                    call_info.setdefault("idp_attributes", {})
                    call_info["idp_attributes"].setdefault(
                        "displayname",
                        call_info.get("remote_display_name")
                        or call_info.get("local_alias")
                        or ""
                    )

                    # First normalize DB payload into a standard envelope
                    base = normalize_policy_response(service_logic.response or {})

                    # Then apply Jinja template to entire structure
                    rendered = apply_template(base, call_info)
                    logger.info("SERVICE RENDERED NAME = %r", (rendered.get("result") or {}).get("name"))
                    logger.info("SERVICE CONTEXT idp_attributes = %r", call_info.get("idp_attributes"))

                    # DO NOT normalize again — keep rendered values verbatim
                    _log_request(rule, request, matched_logic=True, logic_response=rendered)
                    return JsonResponse(rendered, status=200)
            except PolicyLogic.DoesNotExist:
                pass



            # Always-continue override
            if rule.always_continue_service:
                raw_resp = rule.override_service_response or {"action": "continue"}
                rendered = _normalize_service_response(raw_resp)
                _log_request(rule, request, matched_logic=None, is_override=True, override_response=rendered)
                return JsonResponse(rendered, status=200)

            # Upstream passthrough
            if rule.service_target_url:
                resp = httpx.get(
                    rule.service_target_url.rstrip("/") + request.path,
                    params=request.GET,
                    headers=_build_safe_headers(request),
                    auth=((rule.basic_auth_username, rule.basic_auth_password)
                          if rule.basic_auth_username and rule.basic_auth_password else None),
                    timeout=10.0,
                )
                _log_request(rule, request, resp)
                try:
                    upstream = resp.json()
                    return JsonResponse(_normalize_service_response(upstream), status=resp.status_code)
                except ValueError:
                    return JsonResponse({"status": "success", "action": "continue", "result": {"raw": resp.text}}, status=resp.status_code)

            # Default matched rule → safe continue
            return JsonResponse({"status": "success", "action": "continue", "result": {}}, status=200)

        except re.error as e:
            logger.error(f"Regex error in rule {rule.name}: {e}")
            continue

    # No rule matched
    return JsonResponse({"status": "success", "action": "continue", "result": {}}, status=200)


@csrf_exempt
@maybe_basic_auth_protected
def proxy_participant_policy(request):
    logger.info("Received a participant/properties request")

    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    raw_params = dict(request.GET)
    call_info = {k: (v[0] if isinstance(v, list) else v) for k, v in raw_params.items()}

    idp_attrs = {}
    for k, v in list(call_info.items()):
        if k.startswith("idp_attribute_"):
            idp_attrs[k.replace("idp_attribute_", "")] = v
            del call_info[k]
    # if idp_attrs:
    #     call_info["idp_attributes"] = idp_attrs

    if idp_attrs:
        call_info["idp_attributes"] = idp_attrs

        # Persist attributes for future *service* requests
        subject = (
            call_info.get("idp_uuid")
            or call_info.get("remote_alias")
        )

        if subject:
            iv, _ = IdentityValue.objects.get_or_create(subject=subject)
            merged = iv.attrs.copy()
            merged.update(idp_attrs)
            iv.attrs = merged
            iv.save()


    call_info.setdefault("idp_attributes", {})
    call_info["idp_attributes"].setdefault(
        "displayname",
        call_info.get("remote_display_name") or call_info.get("local_alias") or ""
    )

    local_alias = call_info.get("local_alias")
    req_protocol = call_info.get("protocol")
    req_call_direction = call_info.get("call_direction")
    client_ip = _get_client_ip(request)
    client_host = request.get_host().split(":")[0] if request.get_host() else None

    rules = PolicyProxyRule.objects.filter(is_active=True).order_by("priority", "-updated_at")

    for rule in rules:
        try:
            if not re.search(rule.regex, local_alias or ""):
                continue
            if rule.protocols and req_protocol and req_protocol not in rule.protocols:
                continue
            if rule.call_directions and req_call_direction and req_call_direction not in rule.call_directions:
                continue
            if rule.source_match:
                src = rule.source_match.strip().lower()
                if client_ip != src and client_host != src and src not in (client_ip or "") and src not in (client_host or ""):
                    continue

            _increment_rule_usage(rule)

            # PARTICIPANT logic
            try:
                participant_logic = PolicyLogic.objects.get(rule=rule, rule_type="participant", enabled=True)
                match = evaluate_conditions(participant_logic.conditions, call_info)
                if match["matched"]:
                    rendered = apply_template(participant_logic.response or {}, call_info)
                    rendered = normalize_policy_response(rendered)
                    return finalize_response(rendered, call_info)
            except PolicyLogic.DoesNotExist:
                pass

            # Override
            if rule.always_continue_participant:
                raw = rule.override_participant_response or {"action": "continue"}
                rendered = normalize_policy_response(raw)
                return finalize_response(rendered, call_info)

            # Upstream
            if rule.participant_target_url:
                resp = httpx.get(
                    rule.participant_target_url.rstrip("/") + request.path,
                    params=request.GET,
                    headers=_build_safe_headers(request),
                    auth=((rule.basic_auth_username, rule.basic_auth_password)
                          if rule.basic_auth_username and rule.basic_auth_password else None),
                    timeout=10.0,
                )
                try:
                    upstream_json = resp.json()
                except ValueError:
                    upstream_json = {"raw": resp.text}
                return finalize_response(upstream_json, call_info, status=resp.status_code)

            return finalize_response({"action": "continue"}, call_info)

        except re.error as e:
            logger.error(f"Regex error in rule {rule.name}: {e}")
            continue

    return JsonResponse({"status": "success", "action": "continue", "result": {}}, status=200)


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
        # Determine if advanced participant/service logic exist
        from policy_engine.models import PolicyLogic
        logic_exists = PolicyLogic.objects.filter(rule=rule).exists()
        participant_logic = PolicyLogic.objects.filter(rule=rule, rule_type="participant").first()
        service_logic = PolicyLogic.objects.filter(rule=rule, rule_type="service").first()

        return render(
            request,
            "policy_router/rule_form.html",
            {
                "form": form,
                "rule": rule,
                "logic_exists": logic_exists,
                "participant_logic": participant_logic,
                "service_logic": service_logic,
            },
        )

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

@require_GET
def advanced_logic_state(request, rule_id: int):
    """Return the full logic state for a given rule."""
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)
    participant_exists = PolicyLogic.objects.filter(rule=rule, rule_type="participant").exists()
    service_exists = PolicyLogic.objects.filter(rule=rule, rule_type="service").exists()
    logic_exists = participant_exists or service_exists

    return JsonResponse({
        "success": True,
        "rule_id": rule.id,
        "advanced_logic_enabled": bool(rule.advanced_logic_enabled),
        "logic_exists": logic_exists,
        "participant_exists": participant_exists,
        "service_exists": service_exists,
    })


@require_POST
@transaction.atomic
def toggle_advanced_logic(request, rule_id: int):
    """
    Toggle the advanced logic flag on a rule.

    - When enabling: ensure both participant & service PolicyLogic objects exist.
    - When disabling: delete all related PolicyLogic objects.
    """
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)
    enable = not rule.advanced_logic_enabled

    if enable:
        # Create missing logic objects if enabling
        for rtype in ("participant", "service"):
            PolicyLogic.objects.get_or_create(
                rule=rule,
                rule_type=rtype,
                defaults={"enabled": True, "conditions": {}, "response": {}},
            )
    else:
        # Delete all logic objects if disabling
        PolicyLogic.objects.filter(rule=rule).delete()

    # The signal should keep rule.advanced_logic_enabled synced,
    # but we’ll set and save it manually for immediate response
    rule.advanced_logic_enabled = enable
    rule.save(update_fields=["advanced_logic_enabled"])

    # Compute final state to return
    participant_exists = PolicyLogic.objects.filter(rule=rule, rule_type="participant").exists()
    service_exists = PolicyLogic.objects.filter(rule=rule, rule_type="service").exists()
    logic_exists = participant_exists or service_exists

    return JsonResponse({
        "success": True,
        "rule_id": rule.id,
        "advanced_logic_enabled": enable,
        "logic_exists": logic_exists,
        "participant_exists": participant_exists,
        "service_exists": service_exists,
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

@maybe_protected
@require_POST
def reset_match_count(request, rule_id):
    rule = get_object_or_404(PolicyProxyRule, pk=rule_id)
    rule.match_count = 0
    rule.last_matched_at = None
    rule.save(update_fields=["match_count", "last_matched_at"])
    messages.success(request, f"Match count reset for “{rule.name}”.")
    return redirect(request.META.get("HTTP_REFERER", "/"))

@maybe_protected
@require_POST
def reset_all_match_counts(request):
    PolicyProxyRule.objects.update(match_count=0, last_matched_at=None)
    messages.success(request, "Match counts reset for all rules.")
    return redirect(request.META.get("HTTP_REFERER", "/"))