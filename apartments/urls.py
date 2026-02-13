from django.urls import path, include
from .views import *

urlpatterns = [
     path('', ListingView.as_view(), name='listing'),
     path('detail/<int:pk>/', ListingDetailView.as_view(), name='listing_detail'),
     path('apartments/api/',ApartmentsAPI.as_view(), name='apartments_api'),
     path('test/chart', apartment_price_chart_png, name='test-chart'),
]