from django.contrib import admin
from .models import Sublease
# Register your models here.

@admin.register(Sublease)
class SubleaseAdmin(admin.ModelAdmin):
    list_display = ("price","address")
    search_fields = ("address")