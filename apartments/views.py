from django.http import HttpResponse
from django.shortcuts import render
from django.views.generic import ListView, DetailView

from apartments.models import Apartment


# Create your views here.

class ListingView(ListView):
    model = Apartment
    context_object_name = 'listings'
    template_name = 'listings/listing_list.html'


class ListingDetailView(DetailView):
    model = Apartment
    template_name = 'listings/listing_detail.html'
    context_object_name = 'listing'