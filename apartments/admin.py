from django.contrib import admin
from .models import Apartment, LeasingCompany, ApartmentImages, AIRequestLog, FavoriteActionLog
# Register your models here.

@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ("prices","address")

@admin.register(LeasingCompany)
class LeasingCompanyAdmin(admin.ModelAdmin):
    list_display = ("name","address")

@admin.register(ApartmentImages)
class ApartmentImagesAdmin(admin.ModelAdmin):
    list_display = ("apartment","image")

@admin.register(AIRequestLog)
class AIRequestLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "model_name", "mode", "latency_ms", "success")
    list_filter = ("success", "mode", "model_name", "created_at")
    search_fields = ("request_text", "response_text", "error_message")
    readonly_fields = (
        "created_at",
        "user",
        "mode",
        "model_name",
        "request_text",
        "normalized_request",
        "response_text",
        "normalized_response",
        "latency_ms",
        "success",
        "error_message",
    )


@admin.register(FavoriteActionLog)
class FavoriteActionLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "apartment", "action")
    list_filter = ("action", "created_at")
    search_fields = ("user__username", "apartment__name", "apartment__address")
    readonly_fields = ("created_at", "user", "apartment", "action")
