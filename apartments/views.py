from django.db.models import Q
from django.db.models.aggregates import Count
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
        ctx['num_leasing'] = base_qs.values('leasingCompany__name').annotate(total=Count('leasingCompany')).count()
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

def apartment_price_api(request):

    q = list(Apartment.objects.all().values('name', 'price', 'sqft_living').order_by('-price'))

    return JsonResponse({"ok":True, "data":q}, safe=False)

import requests

class StreetMap(View):

    def get(self, request):

        # Prepare parameters for the API request
        params = {
            # Champaign, IL
            "lat": 40.1138,        # Champaign, IL latitude
            "lon": -88.2260,      # Champaign, IL longitude
            "format": "json",
        }

        headers = {
            "User-Agent": "NestFinder/1.0 (lh32@illinois.edu)"
        }

        try:

            output_raw_all = requests.get("https://nominatim.openstreetmap.org/reverse",
                             params=params, headers=headers, timeout=5)

            # Raise an error if the HTTP status code indicates a problem (e.g., 404, 500)
            output_raw_all.raise_for_status()

            # Convert the response (which is text) into a Python dictionary
            # Return the entire raw JSON as-is for exploration
            # (This can be very large so use carefully in production!)
            output_polished_all = output_raw_all.json()
            return JsonResponse(output_polished_all, safe=False)

        # If *any* network or parsing error occurs, handle it gracefully
        except requests.exceptions.RequestException as e:

            # Return a 502 (Bad Gateway) response with an error message
            # This helps us diagnose connectivity or API issues
            return JsonResponse({"ok": False, "error": str(e)}, status=502)

# ========================================
# CSV export for Apartments

import csv
from datetime import datetime

def export_apartments_csv(request):

    #Generate and download a CSV file for all the apartments.
    # STEP 1: Timestamp for unique filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"apartments_{timestamp}.csv"

    # STEP 2: Prepare HttpResponse
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename=\"{filename}\"'

    # STEP 3: CSV writer
    writer = csv.writer(response)

    # Header row
    writer.writerow([
         "name", "address", "price", "floors", "bedrooms", "bathrooms", "sqft_living","leasingCompany"
    ])

    # STEP 4: Query DB
    rows = (
        Apartment.objects
        .select_related("leasingCompany")
        .values_list(
             "name", "address", "price", "floors", "bedrooms", "bathrooms", "sqft_living", "leasingCompany"
        )
        .order_by("price")
    )

    # STEP 5: Write rows
    for row in rows:
        writer.writerow(row)

    # STEP 6: Return response
    return response

# ========================================
# JSON export for Apartments

from datetime import datetime
from django.http import JsonResponse

def export_apartments_json(request):
    """
    Generate and download a JSON file for all apartments.
    Mirrors the CSV export but returns structured JSON data.
    """

    # STEP 1: Query DB (values() returns dictionaries, perfect for JSON)
    rows = list(
        Apartment.objects
        .select_related("leasingCompany")
        .values(
            "name", "address", "price", "floors", "bedrooms", "bathrooms", "sqft_living", "leasingCompany",
        )
        .order_by("price")
    )

    # STEP 2: Build JSON structure with metadata
    json_content = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "record_count": len(rows),
        "apartments": rows,
    }

    # STEP 3: Create JsonResponse with pretty formatting
    response = JsonResponse(json_content, json_dumps_params={"indent": 2})

    # STEP 4: Timestamped filename + download header
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"apartments_{timestamp}.json"
    response["Content-Disposition"] = f'attachment; filename=\"{filename}\"'

    # STEP 5: Return response
    return response
