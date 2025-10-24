# conftest.py
import os
import django
import pytest

@pytest.fixture(scope="session", autouse=True)
def django_setup():
    """Ensure Django is initialized before tests run."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pexip_policy_router.settings")
    django.setup()
