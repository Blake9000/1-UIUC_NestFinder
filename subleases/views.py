import json
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from .models import *

# Create your views here.

def subleasesAPI(request):
    subleases = Sublease.objects.all()
    qs = {}
    qs.update({'subleases':subleases})
    data = {key: list(value.values()) for key, value in qs.items()}
    payload = json.dumps(data, default=str)
    return HttpResponse(payload, content_type="application/json")
