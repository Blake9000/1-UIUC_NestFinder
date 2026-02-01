from django.contrib import admin
from .models import Sublease, SocialMediaSite, SubleaseImages
# Register your models here.

@admin.register(Sublease)
class SubleaseAdmin(admin.ModelAdmin):
    list_display = ("price","address")

@admin.register(SocialMediaSite)
class SocialMediaSiteAdmin(admin.ModelAdmin):
    list_display = ("name","url")

@admin.register(SubleaseImages)
class SubleaseImagesAdmin(admin.ModelAdmin):
    list_display = ("sublease","image")