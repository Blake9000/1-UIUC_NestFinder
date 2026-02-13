from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.generic import ListView, DetailView
from django.shortcuts import render, get_object_or_404
from django.views import View
from apartments.models import Apartment


# Create your views here.

class ListingView(ListView):
    model = Apartment
    context_object_name = 'listings'
    template_name = 'listings/listing_list.html'


class ListingDetailView(View):
    template_name = 'listings/listing_detail.html'

    def get(self, request, pk):
        listing = get_object_or_404(Apartment, pk=pk)

        context = {
            'listing': listing
        }

        return render(request, self.template_name, context)

class ApartmentsAPI(View):
    def get(self,request):
        q = request.GET.get('q')
        apartments = Apartment.objects.all()
        if q:
            apartments = apartments.filter(
                Q(price__icontains=q) |
                Q(address__icontains=q) |
                Q(name__icontains=q) |
                Q(floors__icontains=q) |
                Q(bedrooms__icontains=q) |
                Q(bathrooms__icontains=q) |
                Q(additional_amenities__icontains=q)
            )
        data = list(apartments.values())

        return JsonResponse({"ok":True, "data":data})

