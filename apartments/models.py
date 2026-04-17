from django.conf import settings
from django.db import models
import os
from datetime import datetime


def timestamped_image_path(instance, filename):
    base, ext = os.path.splitext(filename)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    new_name = f"{base}-{timestamp}{ext}"
    return f"apartment_images/{new_name}"


class LeasingCompany(models.Model):
    name = models.TextField(null=True, blank=True)
    url = models.TextField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name or self.url or "LeasingCompany"


class Apartment(models.Model):
    prices = models.JSONField(default=list, null=True, blank=True)
    name = models.TextField(null=True, blank=True)
    address = models.TextField(blank=True, default="")
    leasingCompany = models.ForeignKey(LeasingCompany, on_delete=models.CASCADE, null=True, blank=True)

    apartments_images = models.URLField(null=True, blank=True)
    apartments_url = models.URLField(null=True, blank=True)

    bedrooms = models.IntegerField(null=True, blank=True)
    bathrooms = models.FloatField(null=True, blank=True)
    sqft_living = models.IntegerField(null=True, blank=True)

    floors = models.IntegerField(null=True, blank=True)
    pets = models.BooleanField(null=True, blank=True)
    internet = models.TextField(null=True, blank=True)
    washer_dryer_in_unit = models.BooleanField(null=True, blank=True)
    washer_dryer_out_unit = models.BooleanField(null=True, blank=True)
    furnished = models.BooleanField(null=True, blank=True)
    housing_type = models.TextField(null=True, blank=True)

    date_posted = models.DateTimeField(null=True, blank=True)
    date_scraped = models.DateTimeField(null=True, blank=True)

    additional_amenities = models.JSONField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} at {self.address}".strip()

    def get_absolute_url(self):
        return f"/detail/{self.pk}/"


class ApartmentImages(models.Model):
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=timestamped_image_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class AIRequestLog(models.Model):
    MODE_CHOICES = [
        ("local", "Local RAG"),
        ("api", "API"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    request_text = models.TextField()
    response_text = models.TextField(blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    model_name = models.CharField(max_length=255, blank=True, default="", db_index=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="local", db_index=True)
    success = models.BooleanField(default=True, db_index=True)
    error_message = models.TextField(blank=True)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)
    thinking_tokens = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.model_name or self.mode} @ {self.created_at:%Y-%m-%d %H:%M:%S}"


class FavoriteActionLog(models.Model):
    ACTION_CHOICES = [
        ("push", "Push"),
        ("unpush", "Unpush"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    apartment = models.ForeignKey(Apartment, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        apartment_label = self.apartment.name if self.apartment and self.apartment.name else "Apartment"
        return f"{self.action} {apartment_label}"
