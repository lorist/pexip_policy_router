# pexip_policy_router/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(("policy_router.urls", "policy_router"), namespace="policy_router")),
    path("", include("django.contrib.auth.urls")),
    path("policy-engine/", include("policy_engine.urls", namespace="policy_engine")),
]

#### if running behid an RP like nginx
# import settings
# if settings.DEBUG:
#     urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")