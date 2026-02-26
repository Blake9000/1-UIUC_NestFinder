from django.urls import path, include
from django.contrib.auth.views import LogoutView
from .views import *

urlpatterns = [
     path('about/', about , name='about'),
     path('login/',site_login, name='login'),
     path('register/',user_register, name='register'),
     path('logout/',LogoutView.as_view(next_page='listing'), name='logout'),
 ]