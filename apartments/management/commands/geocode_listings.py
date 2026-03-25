
import time
import urllib.request
import urllib.parse
import json

from django.core.management.base import BaseCommand
from apartments.models import Apartment


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "NestFinder/1.0 (hvela2@illinois.edu)"


def geocode(address: str, city: str, state: str, debug: bool = False) -> tuple[float, float] | None:
    """Try structured query, then free-text fallback. Returns (lat, lng) or None."""

    def _fetch(params: dict) -> tuple[float, float] | None:
        url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
        if debug:
            print(f"    → GET {url}")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if debug:
                    print(f"    ← {len(data)} result(s): {data[:1]}")
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception as e:
            if debug:
                print(f"    ✗ Request error: {e}")
        return None

    # Strategy 1: structured (best for clean addresses)
    result = _fetch({
        "street":  address,
        "city":    city,
        "state":   state,
        "country": "US",
        "format":  "json",
        "limit":   1,
    })
    if result:
        return result

    time.sleep(0.5)

    # Strategy 2: free-text with city (handles abbreviations, periods, etc.)
    result = _fetch({
        "q":      f"{address}, {city}, {state}, US",
        "format": "json",
        "limit":  1,
    })
    if result:
        return result

    time.sleep(0.5)

    # Strategy 3: try Urbana if Champaign failed (they share many streets)
    if city.lower() == "champaign":
        result = _fetch({
            "q":      f"{address}, Urbana, {state}, US",
            "format": "json",
            "limit":  1,
        })

    return result


class Command(BaseCommand):
    help = "Geocode Apartment addresses and store lat/lng on the model."

    def add_arguments(self, parser):
        parser.add_argument("--limit",  type=int,   default=0,           help="Max apartments to process (0 = all).")
        parser.add_argument("--force",  action="store_true",             help="Re-geocode even if coords already exist.")
        parser.add_argument("--debug",  action="store_true",             help="Print full HTTP request/response for each lookup.")
        parser.add_argument("--delay",  type=float, default=1.1,         help="Seconds between requests (Nominatim limit: 1/s).")
        parser.add_argument("--city",   type=str,   default="Champaign", help="Default city to append (default: Champaign).")
        parser.add_argument("--state",  type=str,   default="IL",        help="Default state to append (default: IL).")

    def handle(self, *args, **options):
        limit = options["limit"]
        force = options["force"]
        debug = options["debug"]
        delay = options["delay"]
        city  = options["city"]
        state = options["state"]

        qs = Apartment.objects.all()
        if not force:
            qs = qs.filter(latitude__isnull=True)
        if limit:
            qs = qs[:limit]

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No apartments need geocoding."))
            return

        self.stdout.write(f"Geocoding {total} apartment(s) (city={city}, state={state})...\n")
        ok = skipped = failed = 0

        for apt in qs:
            address = apt.address or apt.name
            if not address:
                self.stdout.write(self.style.WARNING(f"  [{apt.pk}] No address — skipping."))
                skipped += 1
                continue

            result = geocode(address, city, state, debug=debug)
            if result:
                apt.latitude, apt.longitude = result
                apt.save(update_fields=["latitude", "longitude"])
                self.stdout.write(f"  [{apt.pk}] {address[:60]} → {result[0]:.5f}, {result[1]:.5f}")
                ok += 1
            else:
                self.stdout.write(self.style.WARNING(f"  [{apt.pk}] {address[:60]} → NOT FOUND"))
                failed += 1

            time.sleep(delay)

        self.stdout.write(
            self.style.SUCCESS(f"\nDone. {ok} geocoded, {skipped} skipped, {failed} failed.")
        )
