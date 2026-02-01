from django.contrib import admin
from .models import Apartment, LeasingCompany, ApartmentImages
# Register your models here.

@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ("price","address")

@admin.register(LeasingCompany)
class LeasingCompanyAdmin(admin.ModelAdmin):
    list_display = ("name","address")

@admin.register(ApartmentImages)
class ApartmentImagesAdmin(admin.ModelAdmin):
    list_display = ("apartment","image")