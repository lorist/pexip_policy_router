from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(("policy_router.urls", "policy_router"), namespace="policy_router")),
]
