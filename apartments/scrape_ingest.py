# apartments/scrape_ingest.py
from __future__ import annotations

import json
from typing import Any, Dict, Optional

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
        # Use URL if present to reduce duplicates, else fall back to name
        if company_url:
            company, _ = LeasingCompany.objects.get_or_create(
                url=company_url,
                defaults={"name": company_name},
            )
            if company_name and company.name != company_name:
                company.name = company_name
                company.save(update_fields=["name"])
        else:
            company, _ = LeasingCompany.objects.get_or_create(
                name=company_name,
                defaults={"url": company_url},
            )

    apartments_url = (rec.get("apartments_url") or "").strip() or None
    address = (rec.get("address") or "").strip() or None
    name = rec.get("name")

    if not apartments_url and not address:
        return

    lookup = {"apartments_url": apartments_url} if apartments_url else {"address": address or "", "name": name}

    extra = rec.get("additional_amenities") or {}
    extra.setdefault("price_raw", rec.get("price_raw"))
    extra.setdefault("availability_raw", rec.get("availability_raw"))
    extra.setdefault("image_urls", rec.get("image_urls"))

    defaults = {
        "name": name,
        "address": address or name or "",
        "leasingCompany": company,
        "apartments_images": rec.get("apartments_images"),
        "apartments_url": apartments_url,

        # KEY: prices array from scraper
        "prices": rec.get("prices"),

        "bedrooms": rec.get("bedrooms"),
        "bathrooms": rec.get("bathrooms"),
        "sqft_living": rec.get("sqft_living"),

        # these are not in your current spider; will remain None unless you add them there
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
        # update only when key is present (so "missing" keys don't overwrite)
        updatable_fields = [
            "name", "address", "leasingCompany",
            "apartments_images", "apartments_url",
            "prices",
            "bedrooms", "bathrooms", "sqft_living",
            "floors", "pets", "internet",
            "washer_dryer_in_unit", "washer_dryer_out_unit",
            "furnished", "housing_type", "date_posted",
        ]

        changed = False
        for field in updatable_fields:
            if field == "leasingCompany":
                if company is not None and apt.leasingCompany_id != company.id:
                    apt.leasingCompany = company
                    changed = True
                continue

            if field in rec and rec.get(field) is not None:
                setattr(apt, field, rec.get(field))
                changed = True

        apt.additional_amenities = extra
        apt.date_scraped = now
        changed = True

        if changed:
            apt.save()