
"""
Run: pytest -v policy_router/tests/test_service_policy_matching.py
"""

import pytest
import json
from django.http import JsonResponse
from django.test import RequestFactory
from policy_router.models import PolicyProxyRule
from policy_router.views import proxy_service_policy


@pytest.mark.django_db
class TestPolicySourceMatchBehavior:
    def make_request(self, local_alias="room-1", ip="10.0.0.10", forwarded_for=None):
        """Simulate a Django request with optional X-Forwarded-For."""
        rf = RequestFactory()
        headers = {"REMOTE_ADDR": ip}
        if forwarded_for:
            headers["HTTP_X_FORWARDED_FOR"] = forwarded_for
        request = rf.get("/policy/v1/service/configuration", {
            "local_alias": local_alias,
            "protocol": "sip",
            "call_direction": "in",
        }, **headers)
        return request

    def test_rule_without_source_does_not_block_ip_rule(self, db):
        """A rule with no source_match should not block a later IP rule."""
        PolicyProxyRule.objects.create(
            name="alias-only",
            regex=r"room-\d+",
            priority=1,
            is_active=True,
            protocols=["sip"],
            call_directions=["in"],
            source_match=None,
        )

        PolicyProxyRule.objects.create(
            name="ip-match",
            regex=r"room-\d+",
            priority=2,
            is_active=True,
            protocols=["sip"],
            call_directions=["in"],
            source_match="10.0.0.10",
            always_continue_service=True,
            override_service_response={"status": "success", "action": "matched-ip"},
        )

        request = self.make_request(local_alias="room-123", ip="10.0.0.10")
        response = proxy_service_policy(request)
        assert isinstance(response, JsonResponse)
        data = json.loads(response.content)
        assert data["action"] == "matched-ip"

    def test_source_match_normalization_variants(self, db):
        """Variants of 'None', 'null', and spaces should all normalize to None."""
        for variant in ["", " ", "None", "null", "NULL", " none "]:
            rule = PolicyProxyRule.objects.create(
                name=f"rule-{variant.strip() or 'blank'}",
                regex=r"vmr-\d+",
                source_match=variant,
                protocols=["sip"],
                call_directions=["in"],
                always_continue_service=True,
                override_service_response={"action": "normalized"},
            )
            assert rule.source_match is None, f"variant {variant!r} should normalize to None"

    def test_forwarded_for_ip_matching(self, db):
        """Ensure matching works with X-Forwarded-For header."""
        PolicyProxyRule.objects.create(
            name="forwarded-ip",
            regex=r"room-\d+",
            source_match="172.16.0.5",
            protocols=["sip"],
            call_directions=["in"],
            always_continue_service=True,
            override_service_response={"action": "via-forwarded"},
        )
        request = self.make_request(ip="127.0.0.1", forwarded_for="172.16.0.5")
        response = proxy_service_policy(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["action"] == "via-forwarded"

    def test_duplicate_regex_with_distinct_sources_allowed(self, db):
        """Same regex allowed when source_match differs."""
        PolicyProxyRule.objects.create(
            name="src-a",
            regex=r"room-\d+",
            source_match="10.0.0.10",
            protocols=["sip"],
            call_directions=["in"],
            always_continue_service=True,
            override_service_response={"action": "a"},
        )
        # Should not raise ValidationError
        PolicyProxyRule.objects.create(
            name="src-b",
            regex=r"room-\d+",
            source_match="10.0.0.20",
            protocols=["sip"],
            call_directions=["in"],
            always_continue_service=True,
            override_service_response={"action": "b"},
        )
        assert PolicyProxyRule.objects.count() == 2

    def test_identical_regex_and_source_raises(self, db):
        """Two identical regex rules with same source should trigger validation."""
        PolicyProxyRule.objects.create(
            name="dup1",
            regex=r"room-\d+",
            source_match="10.0.0.10",
            protocols=["sip"],
            call_directions=["in"],
            always_continue_service=True,
            override_service_response={"action": "ok"},
        )
        with pytest.raises(Exception):
            PolicyProxyRule.objects.create(
                name="dup2",
                regex=r"room-\d+",
                source_match="10.0.0.10",
                protocols=["sip"],
                call_directions=["in"],
                always_continue_service=True,
                override_service_response={"action": "fail"},
            )
