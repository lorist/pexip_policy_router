from django.urls import path
from . import views

app_name = "policy_router"

urlpatterns = [
    # Proxy endpoints
    path(
        "policy/v1/service/configuration",
        views.proxy_service_policy,
        name="proxy_service_policy",
    ),
    path(
        "policy/v1/participant/properties",
        views.proxy_participant_policy,
        name="proxy_participant_policy",
    ),

    # Rule management
    path("rules/", views.rule_list, name="rule_list"),
    path("rules/create/", views.rule_create, name="rule_create"),
    path("rules/<int:pk>/edit/", views.rule_edit, name="rule_edit"),
    path("rules/<int:pk>/delete/", views.rule_delete, name="rule_delete"),

    # Logs
    path("logs/", views.log_list, name="log_list"),
]
