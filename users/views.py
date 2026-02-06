from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.

def about(request):
    return render(request, 'users/about.html')

def login(request):
    html = render(request, 'users/login.html')
    return HttpResponse(html, content_type='text/html')