from django.urls import path, include
from .views import *

urlpatterns = [
    path('subleases/api/', subleasesAPI, name='subleasesAPI'),
]