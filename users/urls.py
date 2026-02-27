from django.urls import path, include
from .views import about

urlpatterns = [
     path('about/', about , name='about'),
     path('accounts/', include('allauth.urls')),
]