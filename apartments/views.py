import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from time import perf_counter

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Q
from django.db.models.aggregates import Count
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.generic import ListView
from django.shortcuts import render, get_object_or_404
from django.views import View
from apartments.models import AIRequestLog, Apartment, FavoriteActionLog
from io import BytesIO
import requests
from users.models import Favorite
from django.core.exceptions import PermissionDenied

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
        log_favorite_action(request.user, apartment, FavoriteActionLog.ACTION_UNPUSH)
    else:
        Favorite.objects.create(user=request.user, apartment=apartment)
        log_favorite_action(request.user, apartment, FavoriteActionLog.ACTION_PUSH)

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
from django.http import JsonResponse
from NestFinder.secrets_environment import env

MODEL_NAME = "gemini-3.1-flash-lite-preview"


def apartment_chatbot(request):
    if request.method == "GET":
        return render(request, "chatbot/chatbot.html")

    user_message = request.POST.get("message", "").strip()
    mode = request.POST.get("mode", "local").strip().lower()

    if not user_message:
        return JsonResponse({"error": "Message is required."}, status=400)

    apartments = list(Apartment.objects.select_related("leasingCompany").all())
    if not apartments:
        return JsonResponse({"results": []})

    apartment_payload = [serialize_apartment_for_model(apartment) for apartment in apartments]
    model_name = MODEL_NAME if mode == "api" else "Local RAG"
    started_at = perf_counter()

    try:
        if mode == "api":
            top_ids = geminiAPI(user_message, apartment_payload)
        else:
            from .ai_local_rag import rank_apartments_with_local_rag
            top_ids = rank_apartments_with_local_rag(user_message, apartment_payload)

        apartment_map = {apartment.id: apartment for apartment in apartments}
        ranked_apartments = []

        for apartment_id in top_ids:
            apartment = apartment_map.get(apartment_id)
            if apartment and apartment not in ranked_apartments:
                ranked_apartments.append(apartment)

        results = [serialize_apartment_for_frontend(apartment) for apartment in ranked_apartments[:3]]
        latency_ms = round((perf_counter() - started_at) * 1000)

        log_ai_request(
            user=request.user if request.user.is_authenticated else None,
            request_text=user_message,
            response_text=build_ai_response_text(results),
            latency_ms=latency_ms,
            mode=mode,
            model_name=model_name,
            success=True,
        )

        return JsonResponse({"results": results})

    except Exception as exc:
        latency_ms = round((perf_counter() - started_at) * 1000)
        log_ai_request(
            user=request.user if request.user.is_authenticated else None,
            request_text=user_message,
            response_text="",
            latency_ms=latency_ms,
            mode=mode,
            model_name=model_name,
            success=False,
            error_message=str(exc),
        )
        return JsonResponse({"error": str(exc)}, status=500)


def geminiAPI(message: str, apartments: list[dict]) -> list[int]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=env("GEMINI_API_KEY"))
    prompt = build_gemini_ranking_prompt(message, apartments)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=64,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "top_3": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 3,
                        "maxItems": 3,
                    }
                },
                "required": ["top_3"],
            },
        ),
    )

    raw_text = extract_response_text(response)
    return extract_top_ids(raw_text, apartments)


def build_gemini_ranking_prompt(user_query: str, apartments: list[dict]) -> str:
    apartment_lines = []

    for apartment in apartments:
        compact = {
            "id": apartment.get("id"),
            "name": apartment.get("name"),
            "address": apartment.get("address"),
            "price_min": apartment.get("price_min"),
            "price_max": apartment.get("price_max"),
            "bedrooms": apartment.get("bedrooms"),
            "bathrooms": apartment.get("bathrooms"),
            "sqft_living": apartment.get("sqft_living"),
            "pets": apartment.get("pets"),
            "furnished": apartment.get("furnished"),
            "washer_dryer_in_unit": apartment.get("washer_dryer_in_unit"),
            "washer_dryer_out_unit": apartment.get("washer_dryer_out_unit"),
            "housing_type": apartment.get("housing_type"),
            "internet": apartment.get("internet"),
            "leasing_company": apartment.get("leasing_company"),
            "amenities_text": apartment.get("amenities_text"),
        }
        apartment_lines.append(json.dumps(compact, ensure_ascii=False))

    apartment_block = "\n".join(apartment_lines)

    return f"""
    Rank the apartments for this request.

    User request:
    {user_query}

    Apartments:
    {apartment_block}

    Return only JSON:
    {{"top_3":[id1,id2,id3]}}

    Rules:
    - Exactly 3 IDs
    - Best to worst
    - Only use listed IDs
    - No explanation
    """.strip()


def extract_response_text(response) -> str:
    if hasattr(response, "text") and response.text:
        return response.text.strip()

    try:
        parts = response.candidates[0].content.parts
        text_chunks = [part.text for part in parts if hasattr(part, "text") and part.text]
        return "\n".join(text_chunks).strip()
    except Exception:
        return ""


def extract_top_ids(raw_response: str, apartments: list[dict]) -> list[int]:
    valid_ids = {apartment["id"] for apartment in apartments if apartment.get("id") is not None}

    try:
        parsed = json.loads(raw_response)
        values = parsed.get("top_3", [])
        cleaned = []

        for value in values:
            if isinstance(value, int) and value in valid_ids and value not in cleaned:
                cleaned.append(value)

        if len(cleaned) >= 3:
            return cleaned[:3]
    except Exception:
        pass

    try:
        json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
            values = parsed.get("top_3", [])
            cleaned = []

            for value in values:
                if isinstance(value, int) and value in valid_ids and value not in cleaned:
                    cleaned.append(value)

            if len(cleaned) >= 3:
                return cleaned[:3]
    except Exception:
        pass

    numbers = re.findall(r"\d+", raw_response or "")
    cleaned = []

    for num in numbers:
        apartment_id = int(num)
        if apartment_id in valid_ids and apartment_id not in cleaned:
            cleaned.append(apartment_id)

    if len(cleaned) >= 3:
        return cleaned[:3]

    return [apartment["id"] for apartment in apartments[:3] if apartment.get("id") is not None]


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


def build_ai_response_text(results):
    if not results:
        return "No results returned"

    parts = []
    for result in results:
        parts.append(f"#{result.get('id')}: {result.get('name') or 'Unnamed listing'}")
    return " | ".join(parts)


def normalize_analytics_text(value):
    if not value:
        return ""

    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s$#.-]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def log_ai_request(user, request_text, response_text, latency_ms, mode, model_name, success=True, error_message=""):
    try:
        AIRequestLog.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            request_text=request_text,
            normalized_request=normalize_analytics_text(request_text),
            response_text=response_text,
            normalized_response=normalize_analytics_text(response_text),
            latency_ms=max(int(latency_ms or 0), 0),
            mode=mode or "",
            model_name=model_name or "",
            success=success,
            error_message=error_message or "",
        )
    except Exception:
        pass


def log_favorite_action(user, apartment, action):
    try:
        FavoriteActionLog.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            apartment=apartment,
            action=action,
        )
    except Exception:
        pass


def build_daily_counts(items, timestamp_attr="created_at"):
    counts = Counter()

    for item in items:
        dt = getattr(item, timestamp_attr, None)
        if not dt:
            continue
        counts[dt.date().isoformat()] += 1

    return [{"label": label, "count": counts[label]} for label in sorted(counts.keys())]


def build_weekly_counts(items, timestamp_attr="created_at"):
    counts = Counter()

    for item in items:
        dt = getattr(item, timestamp_attr, None)
        if not dt:
            continue
        week_start = (dt.date() - timedelta(days=dt.weekday())).isoformat()
        counts[week_start] += 1

    return [{"label": label, "count": counts[label]} for label in sorted(counts.keys())]


def build_repeat_output_rows(ai_logs, limit=25):
    grouped = defaultdict(list)

    for log in ai_logs:
        if log.success and log.normalized_response:
            grouped[log.normalized_response].append(log)

    rows = []
    cluster_number = 1

    for _, logs in grouped.items():
        unique_requests = []
        seen_requests = set()

        for log in logs:
            normalized_request = log.normalized_request or normalize_analytics_text(log.request_text)
            if normalized_request not in seen_requests:
                seen_requests.add(normalized_request)
                unique_requests.append(log)

        if len(unique_requests) < 2:
            continue

        request_texts = [log.request_text.strip() for log in unique_requests if log.request_text.strip()]
        if len(request_texts) < 2:
            continue

        similarity_scores = []
        for index, left in enumerate(request_texts):
            for right in request_texts[index + 1:]:
                similarity_scores.append(SequenceMatcher(None, left.lower(), right.lower()).ratio())

        avg_similarity = round((sum(similarity_scores) / len(similarity_scores)) if similarity_scores else 1.0, 3)

        rows.append({
            "cluster_id": f"OUT-{cluster_number:03d}",
            "requests": request_texts[:4],
            "output": logs[0].response_text or "No output text stored",
            "similarity_score": avg_similarity,
            "repeat_count": len(logs),
            "distinct_request_count": len(request_texts),
        })
        cluster_number += 1

    rows.sort(key=lambda row: (-row["repeat_count"], row["similarity_score"], -row["distinct_request_count"]))
    return rows[:limit]


@login_required
def analytics_view(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    ai_logs = list(AIRequestLog.objects.all().order_by("created_at"))
    favorite_logs = list(FavoriteActionLog.objects.all().order_by("created_at"))

    ai_latency_series = [
        {
            "label": log.created_at.strftime("%Y-%m-%d %H:%M"),
            "latency_ms": log.latency_ms,
        }
        for log in ai_logs
    ]

    model_latency_map = defaultdict(lambda: {"latencies": [], "count": 0})
    for log in ai_logs:
        model_key = log.model_name or log.mode or "Unknown"
        model_latency_map[model_key]["latencies"].append(log.latency_ms)
        model_latency_map[model_key]["count"] += 1

    model_latency_data = [
        {
            "label": model_name,
            "avg_latency_ms": round(sum(values["latencies"]) / len(values["latencies"]), 2),
            "request_count": values["count"],
        }
        for model_name, values in sorted(model_latency_map.items())
        if values["latencies"]
    ]

    query_counts = Counter()
    query_examples = {}
    for log in ai_logs:
        normalized = log.normalized_request or normalize_analytics_text(log.request_text)
        if not normalized:
            continue
        query_counts[normalized] += 1
        query_examples.setdefault(normalized, log.request_text)

    common_queries_data = [
        {"label": query_examples[key], "count": count}
        for key, count in query_counts.most_common(10)
    ]

    ai_usage_daily = build_daily_counts(ai_logs)
    ai_usage_weekly = build_weekly_counts(ai_logs)
    favorite_usage_daily = build_daily_counts(favorite_logs)
    favorite_usage_weekly = build_weekly_counts(favorite_logs)

    favorite_action_breakdown = {
        "push": sum(1 for log in favorite_logs if log.action == FavoriteActionLog.ACTION_PUSH),
        "unpush": sum(1 for log in favorite_logs if log.action == FavoriteActionLog.ACTION_UNPUSH),
    }

    avg_latency = round(sum(log.latency_ms for log in ai_logs) / len(ai_logs), 2) if ai_logs else 0
    repeat_output_rows = build_repeat_output_rows(ai_logs)

    context = {
        "total_ai_requests": len(ai_logs),
        "avg_ai_latency": avg_latency,
        "unique_query_count": len(query_counts),
        "total_favorite_actions": len(favorite_logs),
        "favorite_push_count": favorite_action_breakdown["push"],
        "favorite_unpush_count": favorite_action_breakdown["unpush"],
        "ai_latency_series": ai_latency_series,
        "model_latency_data": model_latency_data,
        "common_queries_data": common_queries_data,
        "ai_usage_daily": ai_usage_daily,
        "ai_usage_weekly": ai_usage_weekly,
        "favorite_usage_daily": favorite_usage_daily,
        "favorite_usage_weekly": favorite_usage_weekly,
        "repeat_output_rows": repeat_output_rows,
    }

    return render(request, "admin/analytics.html", context)
