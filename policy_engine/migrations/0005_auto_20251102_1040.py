from django.db import migrations

def migrate_action_to_response(apps, schema_editor):
    PolicyLogic = apps.get_model("policy_engine", "PolicyLogic")
    for logic in PolicyLogic.objects.all():
        action_value = getattr(logic, "action", None)

        # Normalize
        if action_value == "reject" or logic.reject_reason:
            logic.response = {
                "status": "success",
                "action": "reject",
                "result": {"reject_reason": logic.reject_reason or "Call rejected"}
            }
        else:
            # allow / continue
            logic.response = {
                "status": "success",
                "action": "continue",
                "result": logic.response.get("result", {}) if isinstance(logic.response, dict) else {}
            }
        logic.save()

def reverse_noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ("policy_engine", "0004_policylogic_action"),
    ]
    operations = [
        migrations.RunPython(migrate_action_to_response, reverse_noop),
        migrations.RemoveField(model_name="policylogic", name="action"),
    ]
