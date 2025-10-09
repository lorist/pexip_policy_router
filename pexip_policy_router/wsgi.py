"""
WSGI config for policy_router project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Detects if 'WEBSITE_HOSTNAME' existis in ENV to use settings_AzureWebApp.py, else use standard settings.py
settings_module = 'pexip_policy_router.settings_AzureWebApp' if 'WEBSITE_HOSTNAME' in os.environ else 'pexip_policy_router.settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

application = get_wsgi_application()