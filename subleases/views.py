import json

from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from .models import *

# Create your views here.

def subleasesAPI(request):
    q = request.GET.get('q')
    subleases = Sublease.objects.all()
    if q:
        subleases = subleases.filter(
            Q(price__icontains=q) |
            Q(address__icontains=q) |
            Q(name__icontains=q) |
            Q(floors__icontains=q) |
            Q(bedrooms__icontains=q) |
            Q(bathrooms__icontains=q) |
            Q(additional_amenities__icontains=q)
        )

    data = list(subleases.values())
    payload = json.dumps({"ok":True, "results":data}, default=str)
    return HttpResponse(payload, content_type="application/json")
