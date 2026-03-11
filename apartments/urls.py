from django.urls import path, include
from .views import *

urlpatterns = [
     path('', ListingView.as_view(), name='listing'),
     path('favorites/', FavoritesView.as_view(), name='favorites'),
     path('favorites/apartment/toggle/<int:pk>/', toggle_favorite_apartment, name='toggle_favorite_apartment'),
     path('detail/<int:pk>/', ListingDetailView.as_view(), name='listing_detail'),
     path('apartments/api/',ApartmentsAPI.as_view(), name='apartments_api'),
     path('apartments/api/pricing', apartment_price_api, name='vega_lite_price_api'),
     path('vega-lite/chart1/', chart1_view, name='vega_lite_chart1'),
     path('vega-lite/chart2/', chart2_view, name='vega_lite_chart2'),
     path('apartments/api/count', apartments_count_api, name='apartments_count_api'),
     path("apartments/api/map/", StreetMap.as_view(), name="api-map"),
     path("export/apartments/", export_apartments_csv, name="export_apartments"),
     path("export/apartments/json/", export_apartments_json, name="export_apartments_json"),
     path("favorites/api/allfavorite/", apartments_favorite_api, name="favorites_api"),
     #path("admin/scraping/", admin.site.admin_view(scraping_admin_view), name="admin_scraping"),
     path("chatbot/", apartment_chatbot, name="apartment_chatbot"),
]