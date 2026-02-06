from django.urls import path, include
from .views import *

urlpatterns = [
     path('', ListingView.as_view(), name='listing'),
    path('detail/<int:primary_key>', ListingDetailView.as_view(), name='listing_detail'),
]