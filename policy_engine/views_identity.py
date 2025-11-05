# policy_engine/views_identity.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .models import IdentityAttribute
from .forms import IdentityAttributeForm

@require_http_methods(["GET", "POST"])
def identity_attribute_list(request):
    if request.method == "POST":
        form = IdentityAttributeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Added new IdP attribute.")
            return redirect("policy_engine:identity_attribute_list")
    else:
        form = IdentityAttributeForm()

    attributes = IdentityAttribute.objects.all()
    return render(request, "policy_engine/identity_attribute_list.html", {
        "form": form,
        "attributes": attributes,
    })


@require_http_methods(["POST"])
def identity_attribute_delete(request, pk):
    attr = get_object_or_404(IdentityAttribute, pk=pk)
    attr.delete()
    messages.success(request, "Attribute removed.")
    return redirect("policy_engine:identity_attribute_list")
