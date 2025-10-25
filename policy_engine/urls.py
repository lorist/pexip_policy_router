from django.urls import path
from . import views

app_name = 'policy_engine'

urlpatterns = [
    path('rules/<int:rule_id>/logic/', views.logic_editor, name='logic_editor'),
    path('rules/<int:rule_id>/decisions/', views.logic_decision_log_list, name='logic_decision_logs'),
    path("logic/overview/", views.logic_overview, name="logic_overview"),

]
