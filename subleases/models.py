from django.db import models
import os
from datetime import datetime

'''
Helper method for naming images
'''
def timestamped_image_path(instance, filename):
    base, ext = os.path.splitext(filename)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    new_name = f"{base}-{timestamp}{ext}"
    return f"sublease_images/{new_name}"



'''
The social media site model will hold information regarding the social media site which we pulled the sublease information from.
'''
class SocialMediaSite(models.Model):
    name = models.TextField(null=True, blank=True)
    url = models.TextField(null=True, blank=True)

'''
The sublease model will hold all the information regarding the sublease we were able to find.
Additionally, we will store the date this info was scraped and when it was posted. Since this is 
scraped, we will drop the posting after a certain amount of time 
'''


class Sublease(models.Model):
    price = models.FloatField(null=True, blank=True)
    address = models.TextField()
    name = models.TextField(null=True, blank=True)
    social_media_site = models.ForeignKey(SocialMediaSite, on_delete=models.CASCADE, null=True, blank=True)
    apartments_images = models.URLField(null=True, blank=True)
    apartments_url = models.URLField(null=True, blank=True)
    bedrooms = models.IntegerField(null=True, blank=True)
    bathrooms = models.IntegerField(null=True, blank=True)
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

    def __str__(self):
        return f"{self.name} at {self.address}"



'''
Extra images stored here
'''


class SubleaseImages(models.Model):
    sublease = models.ForeignKey(Sublease, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=timestamped_image_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.image}"