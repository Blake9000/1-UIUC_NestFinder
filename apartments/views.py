import csv
import json
import re
import time
from datetime import datetime

import requests
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView
from google import genai
from google.genai import types

from NestFinder.secrets_environment import env
from apartments.models import AIRequestLog, Apartment, FavoriteActionLog
from users.models import Favorite
from .ai_local_rag import rank_apartments_with_local_rag


class ListingView(ListView):
    model = Apartment
    context_object_name = "listings"
    template_name = "listings/listing_list.html"

    def get_queryset(self):
        q = self.request.GET.get("q") or self.request.POST.get("q")
        qs = Apartment.objects.all()

        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(address__icontains=q)
                | Q(floors__icontains=q)
                | Q(leasingCompany__name__icontains=q)
                | Q(bedrooms__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        base_qs = self.get_queryset()
        q = self.request.GET.get("q") or self.request.POST.get("q")

        ctx["q"] = q
        ctx["total"] = base_qs.count()
        ctx["num_leasing"] = base_qs.values("leasingCompany__name").annotate(total=Count("leasingCompany")).count()

        if self.request.user.is_authenticated:
            ctx["favorite_ids"] = set(
                Favorite.objects.filter(user=self.request.user, apartment__isnull=False).values_list(
                    "apartment__id", flat=True
                )
            )
        else:
            ctx["favorite_ids"] = set()
        return ctx

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)


class FavoritesView(LoginRequiredMixin, ListView):
    context_object_name = "listings"
    template_name = "users/favorites.html"

    def get_queryset(self):
        q = self.request.GET.get("q") or self.request.POST.get("q")
        qs = Apartment.objects.filter(apartment_favorites__user=self.request.user)

        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(address__icontains=q)
                | Q(floors__icontains=q)
                | Q(leasingCompany__name__icontains=q)
                | Q(bedrooms__icontains=q)
            )
        return qs


class ListingDetailView(View):
    template_name = "listings/listing_detail.html"

    def get(self, request, pk):
        listing = get_object_or_404(Apartment, pk=pk)
        context = {"listing": listing}
        return render(request, self.template_name, context)


class ApartmentsAPI(View):
    def get(self, request):
        q = request.GET.get("q")
        apartments = Apartment.objects.all()
        if q:
            apartments = apartments.filter(
                Q(prices__icontains=q)
                | Q(address__icontains=q)
                | Q(name__icontains=q)
                | Q(floors__icontains=q)
                | Q(bedrooms__icontains=q)
                | Q(bathrooms__icontains=q)
                | Q(additional_amenities__icontains=q)
            )
        data = list(apartments.values())
        return JsonResponse({"ok": True, "data": data})


def apartment_price_api(request):
    rows = []
    for apartment in Apartment.objects.all().order_by("name"):
        prices = normalize_prices(apartment.prices)
        if not prices:
            continue
        rows.append(
            {
                "name": apartment.name or apartment.address or f"Apartment {apartment.pk}",
                "price": prices[0],
                "sqft_living": apartment.sqft_living,
            }
        )
    return JsonResponse({"ok": True, "data": rows}, safe=False)


def chart1_view(request):
    return render(request, "vega_lite_charts/chart1.html")


def chart2_view(request):
    return render(request, "vega_lite_charts/chart2.html")


def apartments_count_api(request):
    counts = {}
    for apartment in Apartment.objects.exclude(date_scraped__isnull=True):
        date_key = apartment.date_scraped.date().isoformat()
        counts[date_key] = counts.get(date_key, 0) + 1

    data = []
    running_total = 0
    for date_key in sorted(counts.keys()):
        running_total += counts[date_key]
        data.append({"date": date_key, "total": running_total})

    return JsonResponse({"ok": True, "data": data}, safe=False)


class StreetMap(View):
    def get(self, request):
        params = {
            "lat": 40.1138,
            "lon": -88.2260,
            "format": "json",
        }
        headers = {"User-Agent": "NestFinder/1.0 (lh32@illinois.edu)"}

        try:
            output_raw_all = requests.get(
                "https://nominatim.openstreetmap.org/reverse",
                params=params,
                headers=headers,
                timeout=5,
            )
            output_raw_all.raise_for_status()
            output_polished_all = output_raw_all.json()
            return JsonResponse(output_polished_all, safe=False)
        except requests.exceptions.RequestException as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=502)


def export_apartments_csv(request):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"apartments_{timestamp}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["name", "address", "prices", "floors", "bedrooms", "bathrooms", "sqft_living", "leasingCompany"])

    rows = (
        Apartment.objects.select_related("leasingCompany")
        .values_list("name", "address", "prices", "floors", "bedrooms", "bathrooms", "sqft_living", "leasingCompany__name")
        .order_by("name")
    )

    for row in rows:
        writer.writerow(row)

    return response


def export_apartments_json(request):
    rows = list(
        Apartment.objects.select_related("leasingCompany")
        .values(
            "name",
            "address",
            "prices",
            "floors",
            "bedrooms",
            "bathrooms",
            "sqft_living",
            "leasingCompany__name",
        )
        .order_by("name")
    )

    json_content = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "record_count": len(rows),
        "apartments": rows,
    }

    response = JsonResponse(json_content, json_dumps_params={"indent": 2})
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"apartments_{timestamp}.json"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def toggle_favorite_apartment(request, pk):
    apartment = get_object_or_404(Apartment, pk=pk)
    fav = Favorite.objects.filter(user=request.user, apartment=apartment).first()

    if fav:
        fav.delete()
        FavoriteActionLog.objects.create(user=request.user, apartment=apartment, action="unpush")
    else:
        Favorite.objects.create(user=request.user, apartment=apartment)
        FavoriteActionLog.objects.create(user=request.user, apartment=apartment, action="push")

    return redirect(request.META.get("HTTP_REFERER") or "listing")


@login_required
def apartments_favorite_api(request):
    total_apartments = Favorite.objects.filter(apartment__isnull=False).count()
    total_subleases = Favorite.objects.filter(sublease__isnull=False).count()
    total_all = Favorite.objects.count()

    data = [
        {"category": "Total Favorites", "count": total_all},
        {"category": "Apartments", "count": total_apartments},
        {"category": "Subleases", "count": total_subleases},
    ]

    return JsonResponse(data, safe=False)


MODEL_NAME = "gemini-3.1-flash-lite-preview"


def apartment_chatbot(request):
    if request.method == "GET":
        return render(request, "chatbot/chatbot.html")

    user_message = request.POST.get("message", "").strip()
    mode = request.POST.get("mode", "local").strip().lower()
    if mode not in {"local", "api"}:
        mode = "local"

    if not user_message:
        return JsonResponse({"error": "Message is required."}, status=400)

    apartments = list(Apartment.objects.select_related("leasingCompany").all())
    if not apartments:
        return JsonResponse({"results": []})

    apartment_payload = [serialize_apartment_for_model(apartment) for apartment in apartments]
    started = time.perf_counter()
    usage_data = {}
    model_name = MODEL_NAME if mode == "api" else "Local RAG"

    try:
        if mode == "api":
            top_ids, usage_data = geminiAPI(user_message, apartment_payload)
        else:
            top_ids = rank_apartments_with_local_rag(user_message, apartment_payload)

        apartment_map = {apartment.id: apartment for apartment in apartments}
        ranked_apartments = []
        for apartment_id in top_ids:
            apartment = apartment_map.get(apartment_id)
            if apartment and apartment not in ranked_apartments:
                ranked_apartments.append(apartment)

        results = [serialize_apartment_for_frontend(apartment) for apartment in ranked_apartments[:3]]
        latency_ms = max(1, int(round((time.perf_counter() - started) * 1000)))

        AIRequestLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            request_text=user_message,
            response_text=json.dumps(results, ensure_ascii=False),
            latency_ms=latency_ms,
            model_name=model_name,
            mode=mode,
            success=True,
            prompt_tokens=usage_data.get("prompt_tokens"),
            output_tokens=usage_data.get("output_tokens"),
            total_tokens=usage_data.get("total_tokens"),
            thinking_tokens=usage_data.get("thinking_tokens"),
        )

        return JsonResponse({"results": results})

    except Exception as exc:
        latency_ms = max(1, int(round((time.perf_counter() - started) * 1000)))
        AIRequestLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            request_text=user_message,
            response_text="",
            latency_ms=latency_ms,
            model_name=model_name,
            mode=mode,
            success=False,
            error_message=str(exc),
            prompt_tokens=usage_data.get("prompt_tokens"),
            output_tokens=usage_data.get("output_tokens"),
            total_tokens=usage_data.get("total_tokens"),
            thinking_tokens=usage_data.get("thinking_tokens"),
        )
        return JsonResponse({"error": str(exc)}, status=500)


def geminiAPI(message: str, apartments: list[dict]) -> tuple[list[int], dict]:
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
    usage_data = extract_usage_metadata(response)
    return extract_top_ids(raw_text, apartments), usage_data


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


def extract_usage_metadata(response) -> dict:
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        return {}

    return {
        "prompt_tokens": coerce_int(_usage_value(usage, "prompt_token_count")),
        "output_tokens": coerce_int(_usage_value(usage, "candidates_token_count")),
        "total_tokens": coerce_int(_usage_value(usage, "total_token_count")),
        "thinking_tokens": coerce_int(_usage_value(usage, "thoughts_token_count")),
    }


def _usage_value(usage, attr_name):
    value = getattr(usage, attr_name, None)
    if value is not None:
        return value
    if isinstance(usage, dict):
        return usage.get(attr_name)
    return None


def coerce_int(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


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


def _format_ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _normalize_query(text):
    return " ".join((text or "").strip().lower().split())


def _normalize_response(text):
    return " ".join((text or "").strip().split())


def _bucket_logs(logs, attr_name):
    daily = {}
    weekly = {}

    for log in logs:
        dt = getattr(log, attr_name)
        if not dt:
            continue
        day_key = dt.date().isoformat()
        week_start = dt.date().fromordinal(dt.date().toordinal() - dt.weekday()).isoformat()
        daily[day_key] = daily.get(day_key, 0) + 1
        weekly[week_start] = weekly.get(week_start, 0) + 1

    daily_points = [{"label": key, "value": daily[key]} for key in sorted(daily.keys())]
    weekly_points = [{"label": key, "value": weekly[key]} for key in sorted(weekly.keys())]
    return daily_points, weekly_points


@login_required
def analytics_view(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    ai_logs = list(AIRequestLog.objects.order_by("created_at"))
    favorite_logs = list(FavoriteActionLog.objects.order_by("created_at"))

    latency_records = [
        {
            "label": _format_ts(log.created_at),
            "latency_ms": log.latency_ms,
            "mode": log.mode,
            "model_name": log.model_name or ("Local RAG" if log.mode == "local" else "API"),
        }
        for log in ai_logs
        if log.latency_ms is not None
    ]

    model_latency_data = [
        {
            "label": row["model_name"] or "Unknown",
            "avg_latency_ms": round(float(row["avg_latency_ms"] or 0), 2),
            "request_count": row["request_count"],
        }
        for row in AIRequestLog.objects.filter(success=True, latency_ms__isnull=False)
        .values("model_name")
        .annotate(avg_latency_ms=Avg("latency_ms"), request_count=Count("id"))
        .order_by("model_name")
    ]

    query_counts = {}
    query_display = {}
    for log in ai_logs:
        key = _normalize_query(log.request_text)
        if not key:
            continue
        query_counts[key] = query_counts.get(key, 0) + 1
        query_display.setdefault(key, log.request_text.strip())

    common_queries = [
        {"label": query_display[key], "count": count}
        for key, count in sorted(query_counts.items(), key=lambda item: (-item[1], query_display[item[0]]))[:10]
    ]

    ai_daily, ai_weekly = _bucket_logs(ai_logs, "created_at")
    favorite_daily, favorite_weekly = _bucket_logs(favorite_logs, "created_at")

    token_records = [
        {
            "label": _format_ts(log.created_at),
            "total_tokens": log.total_tokens,
            "prompt_tokens": log.prompt_tokens,
            "output_tokens": log.output_tokens,
            "model_name": log.model_name or "Unknown",
        }
        for log in ai_logs
        if log.total_tokens is not None
    ]

    total_tokens_sum = sum((log.total_tokens or 0) for log in ai_logs)
    token_request_count = sum(1 for log in ai_logs if log.total_tokens is not None)
    avg_total_tokens = round(total_tokens_sum / token_request_count, 2) if token_request_count else 0

    response_groups = {}
    for log in ai_logs:
        normalized_response = _normalize_response(log.response_text)
        normalized_request = _normalize_query(log.request_text)
        if not normalized_response or not normalized_request:
            continue
        bucket = response_groups.setdefault(
            normalized_response,
            {
                "response_text": log.response_text,
                "request_texts": set(),
                "count": 0,
                "model_names": set(),
            },
        )
        bucket["request_texts"].add(log.request_text.strip())
        bucket["count"] += 1
        if log.model_name:
            bucket["model_names"].add(log.model_name)

    repeated_outputs = []
    cluster_id = 1
    for bucket in sorted(response_groups.values(), key=lambda item: (-item["count"], item["response_text"])):
        if len(bucket["request_texts"]) < 2:
            continue
        request_examples = sorted(bucket["request_texts"])[:3]
        repeated_outputs.append(
            {
                "cluster_id": cluster_id,
                "similarity": 1.0,
                "repeat_count": bucket["count"],
                "request_examples": request_examples,
                "response_text": bucket["response_text"],
                "models": ", ".join(sorted(bucket["model_names"])) if bucket["model_names"] else "Unknown",
            }
        )
        cluster_id += 1

    successful_ai_logs = [log for log in ai_logs if log.success]
    failed_ai_logs = [log for log in ai_logs if not log.success]
    favorite_pushes = sum(1 for log in favorite_logs if log.action == "push")
    favorite_unpushes = sum(1 for log in favorite_logs if log.action == "unpush")

    context = {
        "summary_cards": [
            {"label": "AI requests", "value": len(ai_logs)},
            {"label": "Successful AI requests", "value": len(successful_ai_logs)},
            {"label": "Failed AI requests", "value": len(failed_ai_logs)},
            {"label": "Favorite actions", "value": len(favorite_logs)},
            {"label": "Favorite pushes", "value": favorite_pushes},
            {"label": "Favorite unpushes", "value": favorite_unpushes},
            {"label": "Total API tokens", "value": total_tokens_sum},
            {"label": "Average tokens per tokenized request", "value": avg_total_tokens},
        ],
        "latency_records": latency_records,
        "model_latency_data": model_latency_data,
        "common_queries": common_queries,
        "ai_usage_daily": ai_daily,
        "ai_usage_weekly": ai_weekly,
        "favorite_usage_daily": favorite_daily,
        "favorite_usage_weekly": favorite_weekly,
        "token_records": token_records,
        "repeated_outputs": repeated_outputs[:25],
    }

    return render(request, "admin/analytics.html", context)
