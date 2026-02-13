from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.generic import ListView, DetailView
from django.shortcuts import render, get_object_or_404
from django.views import View
from apartments.models import Apartment
import json
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib
from django.urls import reverse

# Create your views here.

class ListingView(ListView):
    model = Apartment
    context_object_name = 'listings'
    template_name = 'listings/listing_list.html'

    def get_queryset(self):
        q = self.request.GET.get('q') or self.request.POST.get('q')
        qs = Apartment.objects.all()

        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(address__icontains=q) |
                Q(floors__icontains=q) |
                Q(leasingCompany__name__icontains=q) |
                Q(bedrooms__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        base_qs = self.get_queryset()
        q = self.request.GET.get('q') or self.request.POST.get('q')

        ctx['q']=q
        ctx['total'] = base_qs.count()

        return ctx

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)


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



matplotlib.use('Agg')
def apartment_price_chart_png(request):
    rows = Apartment.objects.all().values('name', 'price', 'sqft_living').order_by('-price')

    labels = [r['name']+" - "+str(r["sqft_living"])+"sqft" for r in rows]
    prices = [r['price'] for r in rows]

    fig, ax = plt.subplots(figsize=(10,10), dpi=200 )
    ax.bar(labels, prices)# I could add color
    ax.set_title('Apartment Price Chart Comparison')
    ax.set_ylabel('Rent USD($)')
    ax.set_xticks(ticks=list(range(len(labels))),labels=labels, rotation=45, ha='right')
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return HttpResponse(buf.getvalue(), content_type='image/png')

