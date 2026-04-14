from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db.models import QuerySet

from apartments.models import Apartment
from apartments.ai_local_rag import refresh_apartment_index, INDEX_CACHE_PATH


class Command(BaseCommand):
    help = "Rebuild the apartment embedding index used by the local RAG pipeline."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company",
            type=str,
            default=None,
            help="Filter apartments by leasing company name.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit the number of apartments processed.",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=200,
            help="Iterator chunk size for reading apartments from the database.",
        )
        parser.add_argument(
            "--progress-every",
            type=int,
            default=25,
            help="Print progress every N apartments while building the payload.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Build the payload and report progress, but do not rebuild the index.",
        )

    def handle(self, *args, **options):
        company: Optional[str] = options["company"]
        limit: Optional[int] = options["limit"]
        chunk_size: int = options["chunk_size"]
        progress_every: int = options["progress_every"]
        dry_run: bool = options["dry_run"]

        qs: QuerySet[Apartment] = Apartment.objects.select_related("leasingCompany").order_by("id")

        if company:
            qs = qs.filter(leasingCompany__name__iexact=company)

        total = qs.count()
        if limit is not None:
            total = min(total, limit)

        if total == 0:
            raise CommandError("No apartments matched the requested filters.")

        self.stdout.write(self.style.NOTICE(f"Preparing to index {total} apartments..."))

        payload: List[Dict[str, Any]] = []
        started = time.perf_counter()
        processed = 0

        iterable = qs.iterator(chunk_size=chunk_size)

        for apartment in iterable:
            if limit is not None and processed >= limit:
                break

            prices = apartment.prices or []

            numeric_prices: List[float] = []
            for value in prices:
                try:
                    numeric_prices.append(float(value))
                except (TypeError, ValueError):
                    continue

            payload.append(
                {
                    "id": apartment.id,
                    "name": apartment.name or "",
                    "address": apartment.address or "",
                    "leasing_company": str(apartment.leasingCompany) if apartment.leasingCompany else None,
                    "prices": prices,
                    "price_min": min(numeric_prices) if numeric_prices else None,
                    "price_max": max(numeric_prices) if numeric_prices else None,
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
                    "additional_amenities": apartment.additional_amenities or {},
                    "amenities_text": (
                        json.dumps(apartment.additional_amenities, ensure_ascii=False)
                        if apartment.additional_amenities
                        else ""
                    ),
                }
            )

            processed += 1
            if processed % progress_every == 0 or processed == total:
                elapsed = time.perf_counter() - started
                rate = processed / elapsed if elapsed > 0 else 0.0
                self.stdout.write(
                    f"Built payload for {processed}/{total} apartments "
                    f"({rate:.1f} apartments/sec)"
                )

        self.stdout.write(self.style.SUCCESS(f"Payload complete: {len(payload)} apartments"))

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run only. Index was not rebuilt."))
            return

        self.stdout.write("Refreshing apartment index...")
        index_started = time.perf_counter()

        idx = refresh_apartment_index(payload)

        index_elapsed = time.perf_counter() - index_started
        total_elapsed = time.perf_counter() - started

        indexed_count = len(idx.get("ids", [])) if isinstance(idx, dict) else 0

        self.stdout.write(
            self.style.SUCCESS(
                f"Indexed {indexed_count} apartments in {index_elapsed:.2f}s"
            )
        )
        self.stdout.write(self.style.SUCCESS(f"Cache written to: {INDEX_CACHE_PATH}"))
        self.stdout.write(f"Total elapsed time: {total_elapsed:.2f}s")