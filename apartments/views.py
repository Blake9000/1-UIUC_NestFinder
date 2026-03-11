from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.db.models.aggregates import Count
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.generic import ListView
from django.shortcuts import render, get_object_or_404
from django.views import View
from apartments.models import Apartment
from io import BytesIO
import requests
from users.models import Favorite


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

        if self.request.user.is_authenticated:
            ctx['favorite_ids'] = set(
                Favorite.objects.filter(
                    user=self.request.user,
                    apartment__isnull=False,
                ).values_list('apartment__id', flat=True)
            )
        else:
            ctx['favorite_ids'] = set()
        return ctx

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)



class FavoritesView(LoginRequiredMixin, ListView):
    context_object_name = 'listings'
    template_name = 'users/favorites.html'

    def get_queryset(self):
        q = self.request.GET.get('q') or self.request.POST.get('q')
        qs = Apartment.objects.filter(
            apartment_favorites__user=self.request.user
        )

        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(address__icontains=q) |
                Q(floors__icontains=q) |
                Q(leasingCompany__name__icontains=q) |
                Q(bedrooms__icontains=q)
            )
        return qs


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


'''
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
'''
# lines 104 - 106 is our public API endpoint
def apartment_price_api(request):
    q = list(Apartment.objects.all().values('name', 'price', 'sqft_living').order_by('-price'))
    return JsonResponse({"ok":True, "data":q}, safe=False)

def chart1_view(request):

    return render(request, 'vega_lite_charts/chart1.html')

def chart2_view(request):

    return render(request, 'vega_lite_charts/chart2.html')

def apartments_count_api(request):
    qs = (
        Apartment.objects
        .annotate(date=TruncDate('date_scraped'))
        .values('date')
        .annotate(daily_count=Count('id'))
        .order_by('date')
    )
    data = []
    running_total = 0

    for item in qs:
        if item['date']:
            running_total += item['daily_count']
            data.append({
                "date": str(item['date']),
                "total": running_total
            })

    return JsonResponse({"ok": True, "data": data}, safe=False)


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


@login_required
def toggle_favorite_apartment(request, pk):
    apartment = get_object_or_404(Apartment, pk=pk)
    fav = Favorite.objects.filter(user=request.user, apartment=apartment).first()
    if fav:
        fav.delete()
    else:
        fav = Favorite.objects.create(user=request.user, apartment=apartment)
    return redirect(request.META.get('HTTP_REFERER'), 'listing')


@login_required
def apartments_favorite_api(request):

    total_apartments = Favorite.objects.filter(apartment__isnull=False).count()

    total_subleases = Favorite.objects.filter(sublease__isnull=False).count()

    total_all = Favorite.objects.count()

    data = [
        {"category": "Total Favorites", "count": total_all},
        {"category": "Apartments", "count": total_apartments},
        {"category": "Subleases", "count": total_subleases}
    ]

    return JsonResponse(data, safe=False)

# Ai_llama integration, it's the hugging face model we picked.
from django.shortcuts import render
from django.http import JsonResponse
from .ai_llama import *

def apartment_chatbot(request):
    if request.method == "GET":
        return render(request, "chatbot/chatbot.html")

    user_message = request.POST.get("message", "").strip()
    mode = request.POST.get("mode", "local").strip().lower()

    if not user_message:
        return JsonResponse({"error": "Message is required."}, status=400)

    apartments = list(
        Apartment.objects.select_related("leasingCompany").all()[:75]
    )

    if not apartments:
        return JsonResponse({"results": []})

    apartment_payload = [serialize_apartment_for_model(apartment) for apartment in apartments]

    try:
        if mode == "api":
            """placeholder"""
            # top_ids = rank_apartments_with_api(user_message, apartment_payload)
        else:
            top_ids = rank_apartments_with_llama(user_message, apartment_payload)

        apartment_map = {apartment.id: apartment for apartment in apartments}

        ranked_apartments = []
        for apartment_id in top_ids:
            apartment = apartment_map.get(apartment_id)
            if apartment and apartment not in ranked_apartments:
                ranked_apartments.append(apartment)

        results = [serialize_apartment_for_frontend(apartment) for apartment in ranked_apartments[:3]]

        return JsonResponse({"results": results})

    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


def serialize_apartment_for_model(apartment):
    prices = normalize_prices(apartment.prices)
    additional_amenities = apartment.additional_amenities or {}

    leasing_company_name = None
    if apartment.leasingCompany:
        leasing_company_name = str(apartment.leasingCompany)

    return {
        "id": apartment.id,
        "name": apartment.name or "",
        "address": apartment.address or "",
        "leasing_company": leasing_company_name,
        "prices": prices,
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "bedrooms": apartment.bedrooms,
        "bathrooms": apartment.bathrooms,
        "sqft_living": apartment.sqft_living,
        "floors": apartment.floors,
        "pets": apartment.pets,
        "internet": apartment.internet,
        "washer_dryer_in_unit": apartment.washer_dryer_in_unit,
        "washer_dryer_out_unit": apartment.washer_dryer_out_unit,
        "furnished": apartment.furnished,
        "housing_type": apartment.housing_type,
        "apartments_url": apartment.apartments_url,
        "apartments_images": apartment.apartments_images,
        "date_posted": apartment.date_posted.isoformat() if apartment.date_posted else None,
        "date_scraped": apartment.date_scraped.isoformat() if apartment.date_scraped else None,
        "additional_amenities": additional_amenities,
        "amenities_text": flatten_additional_amenities(additional_amenities),
    }


def serialize_apartment_for_frontend(apartment):
    prices = normalize_prices(apartment.prices)
    price_display = format_price_display(prices)

    amenities = []

    if apartment.pets is True:
        amenities.append("Pets allowed")
    elif apartment.pets is False:
        amenities.append("No pets")

    if apartment.furnished is True:
        amenities.append("Furnished")

    if apartment.washer_dryer_in_unit is True:
        amenities.append("In-unit washer/dryer")
    elif apartment.washer_dryer_out_unit is True:
        amenities.append("Shared washer/dryer")

    if apartment.internet:
        amenities.append(str(apartment.internet))

    if apartment.housing_type:
        amenities.append(str(apartment.housing_type))

    if apartment.leasingCompany:
        amenities.append(f"Leasing: {apartment.leasingCompany}")

    return {
        "id": apartment.id,
        "name": apartment.name or "Unnamed listing",
        "address": apartment.address or "Address unavailable",
        "image": apartment.apartments_images,
        "price_display": price_display,
        "bedrooms": apartment.bedrooms,
        "bathrooms": apartment.bathrooms,
        "sqft_living": apartment.sqft_living,
        "detail_url": apartment.get_absolute_url(),
        "amenities": amenities[:5],
    }


def normalize_prices(prices):
    if not prices:
        return []

    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except Exception:
            return []

    if not isinstance(prices, list):
        return []

    normalized = []
    for value in prices:
        try:
            normalized.append(float(value))
        except (TypeError, ValueError):
            continue

    return sorted(normalized)


def format_price_display(prices):
    if not prices:
        return "Price unknown"
    if len(prices) == 1:
        return f"${prices[0]:.0f}"
    return f"${prices[0]:.0f} - ${prices[-1]:.0f}"


def flatten_additional_amenities(data):
    if not data:
        return ""

    parts = []

    if isinstance(data, dict):
        for key, value in data.items():
            if value in [None, "", [], {}]:
                continue

            pretty_key = str(key).replace("_", " ").strip()

            if isinstance(value, list):
                value_text = ", ".join(str(v) for v in value if v not in [None, ""])
            elif isinstance(value, dict):
                nested_items = []
                for nested_key, nested_value in value.items():
                    if nested_value not in [None, "", [], {}]:
                        nested_items.append(f"{nested_key}: {nested_value}")
                value_text = ", ".join(nested_items)
            else:
                value_text = str(value)

            if value_text:
                parts.append(f"{pretty_key}: {value_text}")

    return " | ".join(parts)
