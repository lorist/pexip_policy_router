import os
import logging
from django.apps import AppConfig
from django.db.models.signals import post_save, post_delete

logger = logging.getLogger("policy_engine.apps")


class PolicyEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "policy_engine"

    def ready(self):
        # Prevent duplicate registration when Django's autoreloader forks
        if os.environ.get("RUN_MAIN") != "true":
            return

        logger.debug("PolicyEngineConfig.ready() executing (main process only)...")

        def sync_rule_logic_flag(sender, instance, signal, **kwargs):
            """Sync PolicyProxyRule.advanced_logic_enabled when PolicyLogic changes."""
            from django.apps import apps

            PolicyLogic = apps.get_model("policy_engine", "PolicyLogic")
            PolicyProxyRule = apps.get_model("policy_router", "PolicyProxyRule")

            rule = instance.rule
            has_logic = PolicyLogic.objects.filter(rule=rule).exists()
            rule_type = getattr(instance, "rule_type", "unknown")

            # Determine signal name safely
            signal_name = "post_save" if signal is post_save else "post_delete"

            if rule.advanced_logic_enabled != has_logic:
                rule.advanced_logic_enabled = has_logic
                rule.save(update_fields=["advanced_logic_enabled"])
                logger.info(
                    "Synced PolicyProxyRule %s (via %s on %s logic): advanced_logic_enabled=%s",
                    rule.id,
                    signal_name,
                    rule_type,
                    has_logic,
                )
            else:
                logger.debug(
                    "PolicyProxyRule %s already consistent (enabled=%s, via %s on %s logic)",
                    rule.id,
                    has_logic,
                    signal_name,
                    rule_type,
                )


        # Connect signals by model label (lazy-load & reload-safe)
        post_save.connect(
            sync_rule_logic_flag, sender="policy_engine.PolicyLogic", weak=False
        )
        post_delete.connect(
            sync_rule_logic_flag, sender="policy_engine.PolicyLogic", weak=False
        )

        logger.debug("Connected PolicyLogic signals by model label (main process only)")

        # Optional: one-time startup resync
        try:
            from django.apps import apps
            PolicyProxyRule = apps.get_model("policy_router", "PolicyProxyRule")
            PolicyLogic = apps.get_model("policy_engine", "PolicyLogic")

            for rule in PolicyProxyRule.objects.all():
                has_logic = PolicyLogic.objects.filter(rule=rule).exists()
                if rule.advanced_logic_enabled != has_logic:
                    rule.advanced_logic_enabled = has_logic
                    rule.save(update_fields=["advanced_logic_enabled"])
                    logger.info(
                        "Startup resync: Rule %s advanced_logic_enabled=%s",
                        rule.id,
                        has_logic,
                    )
        except Exception as e:
            logger.warning("Startup resync skipped: %s", e)
