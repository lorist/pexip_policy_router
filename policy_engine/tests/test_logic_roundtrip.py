import json
import pytest
from django.urls import reverse
from django.test import Client
from policy_engine.models import PolicyProxyRule, PolicyLogic


@pytest.mark.django_db
def test_condition_json_roundtrip():
    """
    Ensure conditions are stored as real JSON, not stringified Python dicts.
    """
    rule = PolicyProxyRule.objects.create(name="Test Rule", regex=".*")

    participant_logic = PolicyLogic.objects.create(
        rule=rule,
        rule_type=PolicyLogic.PARTICIPANT,
        enabled=True,
        conditions={
            "combiner": "all",
            "rules": [
                {"field": "call_direction", "operator": "equals", "value": "dial_in"}
            ],
        },
        response={"remote_alias": "sip:test@example.com"},
    )

    # ✅ Stored correctly in DB
    fetched = PolicyLogic.objects.get(pk=participant_logic.pk)
    assert isinstance(fetched.conditions, dict)
    assert fetched.conditions["combiner"] == "all"
    assert fetched.conditions["rules"][0]["field"] == "call_direction"

    # ✅ JSON round trip
    encoded = json.dumps(fetched.conditions)
    decoded = json.loads(encoded)
    assert decoded == fetched.conditions


@pytest.mark.django_db
def test_logic_editor_template_renders(client):
    """
    The logic editor page must render and embed conditions as JSON inside script blocks.
    """
    rule = PolicyProxyRule.objects.create(name="UI Rule", regex=".*")
    logic = PolicyLogic.objects.create(
        rule=rule,
        rule_type=PolicyLogic.PARTICIPANT,
        enabled=True,
        conditions={"combiner": "all", "rules": []},
        response={},
    )

    url = reverse("policy_engine:logic_editor", args=[rule.id])
    response = client.get(url)

    assert response.status_code == 200
    # Ensure correct script tag is present in output
    assert "participant_conditions_json" in response.content.decode()


@pytest.mark.django_db
def test_preview_api_returns_expected_action(client):
    """
    Ensure the preview evaluates logic and returns correct response.
    """
    rule = PolicyProxyRule.objects.create(name="Preview Test", regex=".*")
    logic = PolicyLogic.objects.create(
        rule=rule,
        rule_type=PolicyLogic.PARTICIPANT,
        enabled=True,
        conditions={
            "combiner": "all",
            "rules": [
                {"field": "call_direction", "operator": "equals", "value": "dial_in"}
            ],
        },
        response={"remote_alias": "sip:allowed@example.com"},
    )

    url = reverse("policy_engine:logic_preview", args=[rule.id])

    payload = {
        "type": "participant",
        "conditions": logic.conditions,
        "response": logic.response,
        "call_info": {"call_direction": "dial_in"},
    }

    response = client.post(url, data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 200

    body = response.json()
    assert "result" in body
    assert body["result"]["remote_alias"] == "sip:allowed@example.com"
