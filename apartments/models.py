# apartments/models.py
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
    prices = models.JSONField(default=list, null=True, blank=True)   # was price
    name = models.TextField(null=True, blank=True)
    address = models.TextField(blank=True, default="")              # allow fallback to name
    leasingCompany = models.ForeignKey(LeasingCompany, on_delete=models.CASCADE, null=True, blank=True)

    apartments_images = models.URLField(null=True, blank=True)
    apartments_url = models.URLField(null=True, blank=True)

    bedrooms = models.IntegerField(null=True, blank=True)           # scraper emits Optional[int]
    bathrooms = models.FloatField(null=True, blank=True)            # scraper emits Optional[float]
    sqft_living = models.IntegerField(null=True, blank=True)        # scraper emits Optional[int]

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