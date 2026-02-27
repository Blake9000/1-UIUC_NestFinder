# apartments/scrape_ingest.py
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Optional

from django.db import transaction
from django.utils import timezone

from .models import Apartment, LeasingCompany


def ingest_greenst_jsonl(path: str) -> int:
    n = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            upsert_apartment_record(rec)
            n += 1
    return n


@transaction.atomic
def upsert_apartment_record(rec: Dict[str, Any]) -> None:
    now = timezone.now()

    company_name = (rec.get("leasing_company_name") or "").strip() or None
    company_url = (rec.get("leasing_company_url") or "").strip() or None

    company: Optional[LeasingCompany] = None
    if company_name or company_url:
        company, _ = LeasingCompany.objects.get_or_create(
            name=company_name,
            defaults={"url": company_url},
        )
        if company_url and company.url != company_url:
            company.url = company_url
            company.save(update_fields=["url"])

    apartments_url = (rec.get("apartments_url") or "").strip()
    address = (rec.get("address") or "").strip()

    if not apartments_url and not address:
        return

    lookup = {"apartments_url": apartments_url} if apartments_url else {"address": address, "name": rec.get("name")}

    extra = rec.get("additional_amenities") or {}
    extra.setdefault("price_raw", rec.get("price_raw"))
    extra.setdefault("availability_raw", rec.get("availability_raw"))
    extra.setdefault("image_urls", rec.get("image_urls"))

    defaults = {
        "name": rec.get("name"),
        "address": address or rec.get("name") or "",
        "leasingCompany": company,
        "apartments_images": rec.get("apartments_images"),
        "bedrooms": rec.get("bedrooms"),
        "bathrooms": rec.get("bathrooms"),
        "sqft_living": rec.get("sqft_living"),
        "floors": rec.get("floors"),
        "pets": rec.get("pets"),
        "internet": rec.get("internet"),
        "washer_dryer_in_unit": rec.get("washer_dryer_in_unit"),
        "washer_dryer_out_unit": rec.get("washer_dryer_out_unit"),
        "furnished": rec.get("furnished"),
        "housing_type": rec.get("housing_type"),
        "date_posted": rec.get("date_posted"),
        "date_scraped": now,
        "additional_amenities": extra,
    }

    apt, created = Apartment.objects.get_or_create(**lookup, defaults=defaults)
    if not created:
        for field in [
            "name", "address", "apartments_images",
            "bedrooms", "bathrooms", "sqft_living",
            "floors", "pets", "internet",
            "washer_dryer_in_unit", "washer_dryer_out_unit",
            "furnished", "housing_type", "date_posted",
        ]:
            if rec.get(field) is not None:
                setattr(apt, field, rec.get(field))

        if company is not None:
            apt.leasingCompany = company

        apt.additional_amenities = extra
        apt.date_scraped = now
        apt.save()