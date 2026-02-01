from django.db import models
from django.contrib.auth.models import User

from subleases.models import Sublease
from apartments.models import Apartment


# Create your models here.
'''
The Profile model will allow us to add favorites to the built in user model.
'''

class Profile (models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    favorites_apartments = models.ForeignKey(Apartment, on_delete=models.CASCADE, null=True, blank=True)
    favorites_sublease = models.ForeignKey(Sublease, on_delete=models.CASCADE, null=True, blank=True)