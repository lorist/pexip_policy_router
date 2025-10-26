SERVICE_CALL_INFO_SCHEMA = {
    "bandwidth": {"type": "number"},
    "breakout_uuid": {"type": "uuid"},
    "call_direction": {
        "type": "enum",
        "choices": ["dial_in", "dial_out", "non_dial"],
    },
    "call_tag": {"type": "string"},
    "display_count": {"type": "number"},
    "has_authenticated_display_name": {"type": "bool"},
    "idp_uuid": {"type": "uuid"},
    "local_alias": {"type": "string"},
    "location": {"type": "string"},
    "ms-subnet": {"type": "string"},
    "node_ip": {"type": "ip"},
    "p_Asserted-Identity": {"type": "string"},
    "previous_service_name": {"type": "string"},
    "protocol": {
        "type": "enum",
        "choices": ["api", "webrtc", "sip", "rtmp", "h323", "teams", "mssip"],
    },
    "pseudo_version_id": {"type": "string"},
    "registered": {"type": "bool"},
    "remote_address": {"type": "ip"},
    "remote_alias": {"type": "string"},
    "remote_display_name": {"type": "string"},
    "remote_port": {"type": "number"},
    "service_name": {"type": "string"},
    "service_tag": {"type": "string"},
    "supports_direct_media": {"type": "bool"},
    "teams_tenant_id": {"type": "string"},
    "telehealth_request_id": {"type": "uuid"},
    "third_party_passcode": {"type": "string"},
    "trigger": {
        "type": "enum",
        "choices": [
            "web", "web_avatar_fetch", "invite", "options", "subscribe", "setup",
            "arq", "lrq", "two_stage_dialing", "teams", "unspecified"
        ],
    },
    "unique_service_name": {"type": "string"},
    "vendor": {"type": "string"},
    "version_id": {"type": "string"},
}


PARTICIPANT_CALL_INFO_SCHEMA = {
    "bandwidth": {"type": "number"},
    "call_direction": {
        "type": "enum",
        "choices": ["dial_in", "dial_out", "non_dial"],
    },
    "call_tag": {"type": "string"},
    "call_uuid": {"type": "uuid"},
    "display_count": {"type": "number"},
    "has_authenticated_display_name": {"type": "bool"},
    "idp_attributes": {"type": "object"},
    "idp_uuid": {"type": "uuid"},
    "local_alias": {"type": "string"},
    "location": {"type": "string"},
    "ms-subnet": {"type": "string"},
    "node_ip": {"type": "ip"},
    "p_Asserted-Identity": {"type": "string"},
    "participant_type": {
        "type": "enum",
        "choices": ["standard", "api", "api_host"],
    },
    "participant_uuid": {"type": "uuid"},
    "preauthenticated_role": {
        "type": "enum",
        "choices": ["guest", "chair", None],
    },
    "previous_service_name": {"type": "string"},
    "protocol": {
        "type": "enum",
        "choices": ["api", "webrtc", "sip", "rtmp", "h323", "teams", "mssip"],
    },
    "pseudo_version_id": {"type": "string"},
    "receive_from_audio_mix": {"type": "string"},
    "registered": {"type": "bool"},
    "remote_address": {"type": "ip"},
    "remote_alias": {"type": "string"},
    "remote_display_name": {"type": "string"},
    "remote_port": {"type": "number"},
    "send_to_audio_mixes_mix_name": {"type": "string"},
    "send_to_audio_mixes_prominent": {"type": "bool"},
    "service_name": {"type": "string"},
    "service_tag": {"type": "string"},
    "supports_direct_media": {"type": "bool"},
    "teams_tenant_id": {"type": "string"},
    "telehealth_request_id": {"type": "uuid"},
    "trigger": {
        "type": "enum",
        "choices": [
            "web", "web_avatar_fetch", "invite", "options", "subscribe", "setup",
            "arq", "lrq", "two_stage_dialing", "teams", "unspecified"
        ],
    },
    "unique_service_name": {"type": "string"},
    "vendor": {"type": "string"},
    "version_id": {"type": "string"},
}


SCHEMAS_BY_TYPE = {
    "service": SERVICE_CALL_INFO_SCHEMA,
    "participant": PARTICIPANT_CALL_INFO_SCHEMA,
}
