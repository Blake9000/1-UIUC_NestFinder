from django.http import HttpResponse
from django.shortcuts import render
from django.views.generic import ListView

from apartments.models import Apartment


# Create your views here.

class ListingView(ListView):
    model = Apartment
    context_object_name = 'listings'
    template_name = 'listings/listing_list.html'
