# policy_router/management/commands/resequence_rules.py
from django.core.management.base import BaseCommand
from policy_router.models import PolicyProxyRule

class Command(BaseCommand):
    help = "Resequence PolicyProxyRule priorities to consecutive integers starting at 1"

    def handle(self, *args, **options):
        rules = PolicyProxyRule.objects.all().order_by("priority", "id")
        count = 0
        for index, rule in enumerate(rules, start=1):
            if rule.priority != index:
                rule.priority = index
                rule.save(update_fields=["priority"])
                count += 1

        if count == 0:
            self.stdout.write(self.style.SUCCESS("✅ Priorities are already sequential."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Resequenced {count} rules to consecutive priorities.")
            )
