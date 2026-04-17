from django.contrib import admin
from .models import Apartment, ApartmentImages, LeasingCompany, AIRequestLog, FavoriteActionLog


@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ("prices", "address")


@admin.register(LeasingCompany)
class LeasingCompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "address")


@admin.register(ApartmentImages)
class ApartmentImagesAdmin(admin.ModelAdmin):
    list_display = ("apartment", "image")


@admin.register(AIRequestLog)
class AIRequestLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "model_name",
        "mode",
        "success",
        "latency_ms",
        "total_tokens",
    )
    list_filter = ("mode", "success", "model_name")
    search_fields = ("request_text", "response_text", "error_message")
    readonly_fields = (
        "created_at",
        "user",
        "request_text",
        "response_text",
        "latency_ms",
        "model_name",
        "mode",
        "success",
        "error_message",
        "prompt_tokens",
        "output_tokens",
        "total_tokens",
        "thinking_tokens",
    )


@admin.register(FavoriteActionLog)
class FavoriteActionLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "apartment")
    list_filter = ("action",)
    search_fields = ("user__username", "apartment__name", "apartment__address")
    readonly_fields = ("created_at", "user", "action", "apartment")
