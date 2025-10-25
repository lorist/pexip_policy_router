from typing import Any, Dict, Optional
from .models import PolicyLogic, PolicyDecisionLog
import logging

logger = logging.getLogger(__name__)

SUPPORTED_OPERATORS = {
    'equals', 'not_equals', 'contains', 'not_contains',
    'in', 'not_in', 'startswith', 'endswith',
    'gt', 'gte', 'lt', 'lte', 'exists', 'not_exists'
}

def _eval_condition(param_value, operator: str, expected) -> bool:
    if operator == 'equals':
        return param_value == expected
    if operator == 'not_equals':
        return param_value != expected
    if operator == 'contains':
        return str(expected) in str(param_value or '')
    if operator == 'not_contains':
        return str(expected) not in str(param_value or '')
    if operator == 'in':
        return param_value in (expected or [])
    if operator == 'not_in':
        return param_value not in (expected or [])
    if operator == 'startswith':
        return str(param_value or '').startswith(str(expected))
    if operator == 'endswith':
        return str(param_value or '').endswith(str(expected))
    if operator == 'gt':
        return param_value > expected
    if operator == 'gte':
        return param_value >= expected
    if operator == 'lt':
        return param_value < expected
    if operator == 'lte':
        return param_value <= expected
    if operator == 'exists':
        return param_value is not None
    if operator == 'not_exists':
        return param_value is None
    return False


def evaluate_policy_logic(rule, rule_type: str, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Evaluate advanced logic for a given rule and request type.
    Logs every evaluation outcome (match or no match) in PolicyDecisionLog.
    """
    try:
        logic = rule.advanced_logic.get(rule_type=rule_type, enabled=True)
    except PolicyLogic.DoesNotExist:
        PolicyDecisionLog.objects.create(
            rule=rule,
            rule_type=rule_type,
            matched=False,
            request_payload=request_data,
            response_payload={},
        )
        return None

    cfg = logic.conditions or {}
    match_mode = cfg.get("match_mode", "all")
    conditions = cfg.get("conditions", [])

    # ✅ Treat "no conditions" as an automatic match
    if not conditions:
        logger.info(f"✅ No conditions defined for {rule.name} ({rule_type}); returning default response")
        response = logic.response
        matched = True
    else:
        results = []
        for cond in conditions:
            param = cond.get("parameter")
            operator = cond.get("operator")
            expected = cond.get("value")
            if not param or operator not in SUPPORTED_OPERATORS:
                results.append(False)
                continue
            actual = request_data.get(param)
            result = _eval_condition(actual, operator, expected)
            logger.debug(f"Evaluating: {param} {operator} {expected} → {result}")
            results.append(result)

        matched = all(results) if match_mode == "all" else any(results)
        response = logic.response if matched else None

    # Always create a decision log
    context_fields = {
        "local_alias": request_data.get("local_alias"),
        "participant_uuid": request_data.get("participant_uuid"),
        "protocol": request_data.get("protocol"),
        "call_direction": request_data.get("call_direction"),
        "remote_display_name": request_data.get("remote_display_name"),
        "remote_alias": request_data.get("remote_alias"),
        "request_id": request_data.get("request_id"),
    }
    try:
        PolicyDecisionLog.objects.create(
            rule=rule,
            rule_type=rule_type,
            matched=matched,
            request_payload=request_data,
            response_payload=response or {},
            **context_fields,
        )
        logger.info(f"DecisionLog created for {rule.name} ({rule_type}) matched={matched}")
    except Exception as e:
        logger.exception(f"Failed to create PolicyDecisionLog for {rule.name}: {e}")

    logger.info(f"Advanced logic evaluated for rule={rule.name}, type={rule_type}, matched={matched}")
    return response
