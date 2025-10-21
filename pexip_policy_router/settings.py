from pathlib import Path
from django.conf import settings

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "unsafe-secret-for-dev"
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "policy_router",
    "widget_tweaks",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pexip_policy_router.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                'django.template.context_processors.static',
                'policy_router.context_processors.app_settings',
            ],
        },
    }
]

WSGI_APPLICATION = "pexip_policy_router.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Australia/Sydney"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/rules'
LOGOUT_REDIRECT_URL = '/login/'

# Authentication toggles
ENABLE_WEB_AUTH = True        # Require login for web views (/rules)
ENABLE_POLICY_AUTH = True     # Require Basic Auth for policy endpoints

# Logging config - https://docs.djangoproject.com/en/5.2/topics/logging/
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False, # Important: Set to False to merge with Django's default loggers
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        '': { # All Modules
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False, # Prevent messages from propagating to parent loggers
        },
    }
}