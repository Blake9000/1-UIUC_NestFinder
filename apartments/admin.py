from django.contrib import admin
from .models import Apartment
# Register your models here.
@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ("price","address")