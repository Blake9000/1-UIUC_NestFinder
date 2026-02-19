from django.urls import path, include
from .views import *

urlpatterns = [
     path('', ListingView.as_view(), name='listing'),
     path('detail/<int:pk>/', ListingDetailView.as_view(), name='listing_detail'),
     path('apartments/api/',ApartmentsAPI.as_view(), name='apartments_api'),
     path('test/chart/', apartment_price_chart_png, name='test_chart'),
     path('apartments/api/pricing', apartment_price_api, name='vega_lite_price_api'),
     path("apartments/api/map/", StreetMap.as_view(), name="api-map"),
]