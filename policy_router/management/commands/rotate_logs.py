# policy_router/management/commands/rotate_logs.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from policy_router.models import PolicyRequestLog

class Command(BaseCommand):
    help = "Deletes PolicyRequestLog entries older than N days"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days to keep logs (default: 30)",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        deleted, _ = PolicyRequestLog.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} old logs"))
