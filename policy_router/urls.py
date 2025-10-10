from django.urls import path
from django.contrib.auth import views as auth_views
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
    path("rules/test/", views.rule_tester, name="rule_tester"),
    path("rules/<int:pk>/duplicate/", views.rule_duplicate, name="rule_duplicate"),
    path("rules/resequence/", views.resequence_rules_view, name="rule_resequence"),
    path("rules/reorder/", views.reorder_rules, name="rule_reorder"),
    path("rules/reorder/", views.rule_reorder, name="rule_reorder"),





    # Logs
    path("logs/", views.log_list, name="log_list"),

    # Auth
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/login/"), name="logout"),

    # CSV import/export
    path("rules/export/", views.export_rules_csv, name="export_rules_csv"),
    path("rules/import/", views.import_rules_csv, name="import_rules_csv"),
    path("rules/manage/", views.manage_rules_view, name="manage_rules"),
]
