from django.db import models

'''
The leasing company model will hold information regarding the company offering to lease the apartments.
'''
class LeasingCompany(models.Model):
    name = models.TextField(null=True, blank=True)
    url = models.TextField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)

'''
The apartment model will hold all the information regarding the apartment offered by the leasing company.
'''

class Apartment(models.Model):
    price = models.FloatField(null=True, blank=True)
    name = models.TextField(null=True, blank=True)
    address = models.TextField()
    leasingCompany = models.ForeignKey(LeasingCompany, on_delete=models.CASCADE, null=True, blank=True)
    apartments_images = models.ImageField(null=True, blank=True)
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

