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
        apartments = Apartment.objects.all()
        qs = {}
        qs.update({'apartments':apartments})
        data = {key: list(value.values()) for key, value in qs.items()}
        return JsonResponse({"ok":True, "data":data})


# ------ Chart API & Matplotlib png chart --------
def ApartmentsPriceAPI(request):
    rows = Apartment.objects.all('name', 'price').order_by('-price')
    return JsonResponse({"ok":True, "data":rows})

import json, urllib.request
from io import BytesIO
import matplotlib.pyplot as plt
from django.urls import reverse

def apartment_price_chart_png(request):
    api_url = request.build_absolute_uri(reverse('apartments:price-chart'))

    #fetching json data from the API
    with urllib.request.urlopen(api_url) as resp:
        payload = json.load(resp)

    #extracring rows
    rows = payload.get('results', [])

    labels = [r['name'] for r in rows]
    prices = [r['price'] for r in rows]

    # Creating the bar chart (this is temporary)
    fig, ax = plt.subplots(figsize=(10,10), dpi=200 )
    ax.bar(labels, prices)# I could add color
    ax.set_title('Apartment Price Chart Comparison')
    ax.set_ylabel('Rent USD($)')
    ax.set_xticks(labels, rotation=90, ha='right')
    fig.tight_layout()

    # Converting chart to a PNG in RAM
    buf = BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return HttpResponse(buf.getvalue(), content_type='image/png')


