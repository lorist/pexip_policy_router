from django.urls import path
# from .views import logic_editor, preview_logic
from . import views

app_name = "policy_engine"

urlpatterns = [
    path("<int:rule_id>/", views.logic_editor, name="logic_editor"),
    # path("<int:rule_id>/preview/", views.preview_logic, name="preview_logic"),
    path("<int:rule_id>/preview/", views.logic_preview, name="logic_preview"),
    # path("preview_response/", views.preview_response, name="preview_response"),
    path("preview_logic/<int:rule_id>/", views.preview_response, name="preview_response"),
    path("test-signal/", views.test_signal, name="test_signal"),
]

