from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth import authenticate
import base64

def basic_auth_django_user(view_func):
    def wrapper(request, *args, **kwargs):
        if not settings.ENABLE_POLICY_AUTH:
            return view_func(request, *args, **kwargs)

        auth_header = request.META.get("HTTP_AUTHORIZATION")

        if not auth_header or not auth_header.startswith("Basic "):
            response = HttpResponse("Authentication required", status=401)
            response["WWW-Authenticate"] = 'Basic realm="Policy Router"'
            return response

        try:
            auth_decoded = base64.b64decode(auth_header.split(" ")[1]).decode("utf-8")
            username, password = auth_decoded.split(":", 1)
        except Exception:
            return HttpResponse("Invalid Authorization header", status=400)

        user = authenticate(username=username, password=password)
        if user and user.is_active:
            request.user = user
            return view_func(request, *args, **kwargs)

        response = HttpResponse("Unauthorized", status=401)
        response["WWW-Authenticate"] = 'Basic realm="Policy Router"'
        return response

    return wrapper
