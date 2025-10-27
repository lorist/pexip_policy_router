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

PARTICIPANT_RESPONSE_SCHEMA = {
    "bypass_lock": {"type": "bool", "default": False},
    "call_tag": {"type": "string"},
    "can_receive_personal_mix": {"type": "bool", "default": False},
    "display_count": {"type": "number"},
    "disable_overlay_text": {"type": "bool", "default": False},
    "layout_group": {"type": "string"},
    "preauthenticated_role": {
        "type": "enum",
        "choices": ["chair", "guest", None],
    },
    "prefers_multiscreen_mix": {"type": "bool"},
    "reject_reason": {"type": "string"},
    "remote_alias": {"type": "string"},
    "remote_display_name": {"type": "string"},
    "rx_presentation_policy": {
        "type": "enum",
        "choices": ["ALLOW", "DENY"],
        "default": "ALLOW",
    },
    "spotlight": {"type": "number"},
    "send_to_audio_mixes": {"type": "list"},
    "receive_from_audio_mix": {"type": "string"},
    "wants_presentation_in_mix": {"type": "bool"},
}

AUTOMATIC_PARTICIPANT_SCHEMA = {
    "local_alias": {"type": "string", "required": True, "description": "The calling or 'from' alias."},
    "protocol": {
        "type": "enum",
        "choices": ["h323", "sip", "mssip", "rtmp"],
        "required": True,
        "description": "Protocol to use to place the outgoing call."
    },
    "remote_alias": {"type": "string", "required": True, "description": "Alias of the endpoint to call."},
    "role": {
        "type": "enum",
        "choices": ["chair", "guest"],
        "required": True,
        "description": "Privileges in the conference."
    },
    "call_type": {
        "type": "enum",
        "choices": ["video", "video-only", "audio"],
        "required": False,
        "description": "Call capability."
    },
    "dtmf_sequence": {"type": "string", "required": False, "description": "DTMF sequence to send after call connects."},
    "keep_conference_alive": {
        "type": "enum",
        "choices": [
            "keep_conference_alive",
            "keep_conference_alive_if_multiple",
            "keep_conference_alive_never"
        ],
        "required": False,
        "description": "Determines whether the conference ends automatically."
    },
    "local_display_name": {"type": "string", "required": False, "description": "Display name for the calling alias."},
    "presentation_url": {"type": "string", "required": False, "description": "RTMP presentation stream destination."},
    "remote_display_name": {"type": "string", "required": False, "description": "Friendly name for this participant."},
    "routing": {
        "type": "enum",
        "choices": ["manual", "routing_rule"],
        "required": False,
        "description": "Routing mode for the call."
    },
    "streaming": {"type": "bool", "required": False, "description": "Whether this participant is a streaming/recording device."},
    "system_location_name": {"type": "string", "required": False, "description": "System location for call placement."}
}

SERVICE_RESPONSE_SCHEMA = {
    # === Core Required Fields ===
    "name": {
        "type": "string",
        "required": True,
        "description": "Name of the service (unique per instance)."
    },
    "service_tag": {
        "type": "string",
        "required": True,
        "description": "Unique identifier used to track usage of the service."
    },
    "service_type": {
        "type": "enum",
        "choices": ["conference", "lecture", "gateway", "two_stage_dialing"],
        "required": True,
        "description": "Determines which type of service configuration this response defines."
    },

    # === Shared fields (common across most services) ===
    "description": {"type": "string"},
    "bypass_proxy": {"type": "bool", "default": False},
    "crypto_mode": {
        "type": "enum",
        "choices": [None, "besteffort", "on", "off"],
        "default": None
    },
    "ivr_theme_name": {"type": "string"},
    "local_display_name": {"type": "string"},
    "max_callrate_in": {"type": "number"},
    "max_callrate_out": {"type": "number"},
    "max_pixels_per_second": {
        "type": "enum",
        "choices": [None, "sd", "hd", "fullhd"],
        "default": None
    },
    "prefer_ipv6": {
        "type": "enum",
        "choices": ["default", "yes", "no"],
        "default": "default"
    },
    "enable_overlay_text": {"type": "bool", "default": False},
    "enable_active_speaker_indication": {"type": "bool", "default": False},
    "view": {
        "type": "enum",
        "choices": [
            "one_main_zero_pips", "one_main_seven_pips", "one_main_twentyone_pips",
            "two_mains_twentyone_pips", "one_main_thirtythree_pips", "four_mains_zero_pips",
            "nine_mains_zero_pips", "sixteen_mains_zero_pips", "twentyfive_mains_zero_pips",
            "five_mains_seven_pips", "one_main_one_pip", "one_main_nine_around",
            "one_main_twelve_around", "two_mains_eight_around", "teams"
        ],
        "default": "one_main_seven_pips",
        "applies_to": ["conference", "lecture", "gateway"]
    },

    # === Conference & Lecture ===
    "allow_guests": {"type": "bool", "default": False, "applies_to": ["conference", "lecture"]},
    "automatic_participants": {
        "type": "list",
        "item_schema": AUTOMATIC_PARTICIPANT_SCHEMA,
        "required": False,
        "description": "Participants automatically dialed when the service starts."
    },
    "breakout_rooms": {"type": "bool", "default": False, "applies_to": ["conference", "lecture"]},
    "call_type": {
        "type": "enum",
        "choices": ["video", "video-only", "audio"],
        "default": "video",
        "applies_to": ["conference", "lecture", "two_stage_dialing"]
    },
    "denoise_enabled": {"type": "bool", "default": False, "applies_to": ["conference", "lecture"]},
    "direct_media": {
        "type": "enum",
        "choices": ["best_effort", "always", "never"],
        "default": "never",
        "applies_to": ["conference", "lecture"]
    },
    "direct_media_notification_duration": {"type": "number", "default": 0, "applies_to": ["conference", "lecture"]},
    "enable_chat": {
        "type": "enum",
        "choices": ["default", "yes", "no"],
        "default": "default",
        "applies_to": ["conference", "lecture"]
    },
    "guest_pin": {"type": "string", "applies_to": ["conference", "lecture"]},
    "guests_can_present": {"type": "bool", "default": True, "applies_to": ["conference", "lecture"]},
    "locked": {"type": "bool", "default": False, "applies_to": ["conference", "lecture"]},
    "mute_all_guests": {"type": "bool", "default": False, "applies_to": ["conference", "lecture"]},
    "participant_limit": {"type": "number", "applies_to": ["conference", "lecture"]},
    "pin": {"type": "string", "applies_to": ["conference", "lecture"]},
    "softmute_enabled": {"type": "bool", "default": False, "applies_to": ["conference", "lecture"]},
    "force_presenter_into_main": {"type": "bool", "default": False, "applies_to": ["lecture"]},
    "guest_view": {"type": "string", "applies_to": ["lecture"]},
    "host_view": {"type": "string", "applies_to": ["lecture"]},
    "guests_can_see_guests": {
        "type": "enum",
        "choices": ["no_hosts", "always", "never"],
        "default": "no_hosts",
        "applies_to": ["lecture"]
    },

    # === Gateway ===
    "local_alias": {"type": "string", "required": True, "applies_to": ["gateway"]},
    "remote_alias": {"type": "string", "required": True, "applies_to": ["gateway"]},
    "outgoing_protocol": {
        "type": "enum",
        "choices": ["sip", "h323", "mssip", "rtmp", "gms", "teams"],
        "required": True,
        "applies_to": ["gateway"]
    },
    "called_device_type": {
        "type": "enum",
        "choices": [
            "external", "registration", "mssip_conference_id", "mssip_server",
            "gms_conference", "teams_conference", "teams_user", "telehealth_profile"
        ],
        "default": "external",
        "applies_to": ["gateway"]
    },
    "denoise_audio": {"type": "bool", "default": True, "applies_to": ["gateway"]},
    "dtmf_sequence": {"type": "string", "applies_to": ["gateway"]},
    "external_participant_avatar_lookup": {
        "type": "enum",
        "choices": ["default", "yes", "no"],
        "default": "default",
        "applies_to": ["gateway"]
    },
    "gms_access_token_name": {"type": "string", "applies_to": ["gateway", "two_stage_dialing"]},
    "h323_gatekeeper_name": {"type": "string", "applies_to": ["gateway"]},
    "mssip_proxy_name": {"type": "string", "applies_to": ["gateway", "two_stage_dialing"]},
    "outgoing_location_name": {"type": "string", "applies_to": ["gateway"]},
    "sip_proxy_name": {"type": "string", "applies_to": ["gateway"]},
    "stun_server_name": {"type": "string", "applies_to": ["gateway"]},
    "teams_fit_to_frame": {
        "type": "enum",
        "choices": ["yes", "no"],
        "default": "no",
        "applies_to": ["gateway"]
    },
    "teams_proxy_name": {"type": "string", "applies_to": ["gateway", "two_stage_dialing"]},
    "transcoding_enabled": {"type": "bool", "default": True, "applies_to": ["gateway"]},
    "treat_as_trusted": {"type": "bool", "applies_to": ["gateway"]},
    "turn_server_name": {"type": "string", "applies_to": ["gateway"]},

    # === Virtual Reception (two_stage_dialing) ===
    "match_string": {"type": "string", "applies_to": ["two_stage_dialing"]},
    "post_match_string": {"type": "string", "applies_to": ["two_stage_dialing"]},
    "post_replace_string": {"type": "string", "applies_to": ["two_stage_dialing"]},
    "replace_string": {"type": "string", "applies_to": ["two_stage_dialing"]},
    "system_location_name": {"type": "string", "applies_to": ["two_stage_dialing"]},
    "two_stage_dial_type": {
        "type": "enum",
        "choices": ["regular", "mssip", "gms", "teams"],
        "default": "regular",
        "applies_to": ["two_stage_dialing"]
    }
}

SCHEMAS_BY_TYPE = {
    "service": SERVICE_CALL_INFO_SCHEMA,
    "participant": PARTICIPANT_CALL_INFO_SCHEMA,
}
