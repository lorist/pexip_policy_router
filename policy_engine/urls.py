from django.urls import path
# from .views import logic_editor, preview_logic
from . import views
from .views_identity import identity_attribute_list, identity_attribute_delete
app_name = "policy_engine"

urlpatterns = [
    path("<int:rule_id>/", views.logic_editor, name="logic_editor"),
    path("<int:rule_id>/preview/", views.logic_preview, name="logic_preview"),
    path("<int:rule_id>/logic-preview/", views.logic_preview, name="logic_preview"),
    path("test-signal/", views.test_signal, name="test_signal"),
    path("identity-attributes/", identity_attribute_list, name="identity_attribute_list"),
    path("identity-attributes/<int:pk>/delete/", identity_attribute_delete, name="identity_attribute_delete"),
]

