"""
a combined integration test that ensures service and participant policy routes both respect rule priorities, 
do not block each other, 
and consistently apply source and alias logic
Run: pytest -v policy_router/tests/test_policy_integration.py
"""

import pytest
import json
from django.http import JsonResponse
from django.test import RequestFactory
from policy_router.models import PolicyProxyRule
from policy_router.views import proxy_service_policy, proxy_participant_policy


@pytest.mark.django_db
class TestPolicyIntegrationBehavior:
    def make_request(self, path, local_alias="room-1", ip="10.0.0.10"):
        rf = RequestFactory()
        request = rf.get(path, {
            "local_alias": local_alias,
            "protocol": "sip",
            "call_direction": "in",
        }, REMOTE_ADDR=ip)
        return request

    def test_service_and_participant_respect_priority(self, db):
        """
        Ensure that lower priority number wins for both service and participant policies.
        """
        PolicyProxyRule.objects.create(
            name="high-priority-service",
            regex=r"room-\d+",
            source_match="10.0.0.10",
            priority=1,
            is_active=True,
            protocols=["sip"],
            call_directions=["in"],
            always_continue_service=True,
            override_service_response={"action": "service-high"},
        )

        PolicyProxyRule.objects.create(
            name="low-priority-service",
            regex=r"room-\d+",
            source_match="10.0.0.10",
            priority=5,
            is_active=True,
            protocols=["sip"],
            call_directions=["in"],
            always_continue_service=True,
            override_service_response={"action": "service-low"},
        )

        PolicyProxyRule.objects.create(
            name="high-priority-participant",
            regex=r"room-\d+",
            source_match="10.0.0.10",
            priority=1,
            is_active=True,
            protocols=["sip"],
            call_directions=["in"],
            always_continue_participant=True,
            override_participant_response={"action": "participant-high"},
        )

        PolicyProxyRule.objects.create(
            name="low-priority-participant",
            regex=r"room-\d+",
            source_match="10.0.0.10",
            priority=5,
            is_active=True,
            protocols=["sip"],
            call_directions=["in"],
            always_continue_participant=True,
            override_participant_response={"action": "participant-low"},
        )

        # Service Policy should pick high-priority
        service_req = self.make_request("/policy/v1/service/configuration")
        service_res = proxy_service_policy(service_req)
        assert service_res.status_code == 200
        data = json.loads(service_res.content)
        assert data["action"] == "service-high"

        # Participant Policy should pick high-priority
        part_req = self.make_request("/policy/v1/participant/properties")
        part_res = proxy_participant_policy(part_req)
        assert part_res.status_code == 200
        data = json.loads(part_res.content)
        assert data["action"] == "participant-high"

    def test_service_and_participant_do_not_block_each_other(self, db):
        """
        Confirm that service and participant policies act independently.
        """
        PolicyProxyRule.objects.create(
            name="service-only",
            regex=r"room-\d+",
            source_match="10.0.0.10",
            protocols=["sip"],
            call_directions=["in"],
            always_continue_service=True,
            override_service_response={"action": "service-only"},
        )

        PolicyProxyRule.objects.create(
            name="participant-only",
            regex=r"room-\d+",
            source_match="10.0.0.10",
            protocols=["sip"],
            call_directions=["in"],
            always_continue_participant=True,
            override_participant_response={"action": "participant-only"},
        )

        # Ensure each policy responds correctly without interfering
        service_req = self.make_request("/policy/v1/service/configuration")
        service_res = proxy_service_policy(service_req)
        data_service = json.loads(service_res.content)
        assert data_service["action"] == "service-only"

        part_req = self.make_request("/policy/v1/participant/properties")
        part_res = proxy_participant_policy(part_req)
        data_part = json.loads(part_res.content)
        assert data_part["action"] == "participant-only"

    def test_service_and_participant_independent_sources(self, db):
        """
        Ensure that a rule restricted to one IP doesn't block another source.
        """
        PolicyProxyRule.objects.create(
            name="specific-source",
            regex=r"room-\d+",
            source_match="192.168.1.100",
            protocols=["sip"],
            call_directions=["in"],
            always_continue_service=True,
            override_service_response={"action": "restricted"},
            always_continue_participant=True,
            override_participant_response={"action": "restricted"},
        )

        # Request from different IP should skip rule gracefully
        req_service = self.make_request("/policy/v1/service/configuration", ip="10.0.0.99")
        res_service = proxy_service_policy(req_service)
        assert res_service.status_code == 404  # No match

        req_participant = self.make_request("/policy/v1/participant/properties", ip="10.0.0.99")
        res_participant = proxy_participant_policy(req_participant)
        assert res_participant.status_code == 404  # No match
