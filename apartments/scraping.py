from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.http import Response


GREENST_BASE_URL = "https://www.greenstrealty.com"
GREENST_PROPERTIES_URLS = [
    "https://www.greenstrealty.com/properties",
    "https://www.greenstrealty.com/properties/search/student",
    "https://www.greenstrealty.com/properties/search/residential",
]

@dataclass
class ApartmentRecord:
    leasing_company_name: str
    leasing_company_url: str

    apartments_url: str
    name: Optional[str] = None
    address: Optional[str] = None

    prices: Optional[List[float]] = None

    availability_raw: Optional[str] = None
    price_raw: Optional[str] = None

    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft_living: Optional[int] = None

    apartments_images: Optional[str] = None
    image_urls: Optional[List[str]] = None

    pets: Optional[bool] = None
    furnished: Optional[bool] = None
    washer_dryer_in_unit: Optional[bool] = None
    washer_dryer_out_unit: Optional[bool] = None
    internet: Optional[str] = None

    housing_type: Optional[str] = None
    additional_amenities: Optional[Dict[str, Any]] = None

    date_posted: Optional[datetime] = None
    date_scraped: Optional[datetime] = None


_price_money_re = re.compile(r"\$[\d,]+(?:\.\d+)?")

def absolutize(url: Optional[str]) -> Optional[str]:
    if not url:
        return url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return f"{GREENST_BASE_URL}{url}"
    return f"{GREENST_BASE_URL}/{url}"

def clean_text(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s or None

def maybe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None

def maybe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None

def parse_prices_from_values(*values: Any) -> Optional[List[float]]:
    out: List[float] = []

    for value in values:
        if value is None:
            continue

        if isinstance(value, (int, float)):
            out.append(float(value))
            continue

        text = str(value)
        matches = _price_money_re.findall(text)
        if matches:
            for m in matches:
                n = m.replace("$", "").replace(",", "")
                try:
                    out.append(float(n))
                except ValueError:
                    continue
            continue

        for part in re.split(r"[-/]| to ", text):
            part = part.strip().replace(",", "")
            if not part:
                continue
            try:
                out.append(float(part))
            except ValueError:
                continue

    deduped: List[float] = []
    seen = set()
    for p in out:
        if p not in seen:
            seen.add(p)
            deduped.append(p)

    return deduped or None

def extract_floorplan_summary(fplans: List[Dict[str, Any]]) -> Tuple[
    Optional[List[float]],
    Optional[str],
    Optional[int],
    Optional[float],
    Optional[int],
]:
    all_prices: List[float] = []
    availabilities: List[str] = []
    bedrooms: List[int] = []
    bathrooms: List[float] = []
    sqfts: List[int] = []

    for fp in fplans:
        if not isinstance(fp, dict):
            continue

        fp_prices = parse_prices_from_values(
            fp.get("total_price"),
            fp.get("price_per_bed"),
        )
        if fp_prices:
            all_prices.extend(fp_prices)

        availability = clean_text(fp.get("availability"))
        if availability:
            availabilities.append(availability)

        beds = maybe_int(fp.get("beds"))
        if beds is not None:
            bedrooms.append(beds)

        baths = maybe_float(fp.get("baths"))
        if baths is not None:
            bathrooms.append(baths)

        sqft = maybe_int(fp.get("sqft"))
        if sqft is not None:
            sqfts.append(sqft)

    price_values = parse_prices_from_values(all_prices)
    availability_raw = " | ".join(dict.fromkeys(availabilities)) if availabilities else None
    bedrooms_value = min(bedrooms) if bedrooms else None
    bathrooms_value = min(bathrooms) if bathrooms else None
    sqft_value = max(sqfts) if sqfts else None

    return price_values, availability_raw, bedrooms_value, bathrooms_value, sqft_value

def derive_flags_from_text(payload: Dict[str, Any]) -> Dict[str, Any]:
    haystack_parts: List[str] = []

    for key in ("title", "subtitle", "type_of_property", "property_area", "amenities"):
        val = payload.get(key)
        if val:
            haystack_parts.append(str(val))

    for fp in payload.get("fplans") or []:
        if isinstance(fp, dict):
            for key in ("title", "availability", "floorplan_text"):
                val = fp.get(key)
                if val:
                    haystack_parts.append(str(val))

    text = " ".join(haystack_parts).lower()

    pets = None
    if "pet" in text:
        pets = True

    furnished = True if "furnished" in text else None

    washer_dryer_in_unit = None
    washer_dryer_out_unit = None
    if "in-unit washer" in text or "in unit washer" in text:
        washer_dryer_in_unit = True
    if "on-site laundry" in text or "shared laundry" in text or "laundry facility" in text:
        washer_dryer_out_unit = True

    internet = None
    if "internet" in text:
        internet = "Mentioned"

    return {
        "pets": pets,
        "furnished": furnished,
        "washer_dryer_in_unit": washer_dryer_in_unit,
        "washer_dryer_out_unit": washer_dryer_out_unit,
        "internet": internet,
    }

def build_price_raw(payload: Dict[str, Any], parsed_prices: Optional[List[float]]) -> Optional[str]:
    prices_structured = payload.get("prices") or {}

    bedlow = prices_structured.get("bedlow")
    bedhigh = prices_structured.get("bedhigh")
    totlow = prices_structured.get("totlow")
    tothigh = prices_structured.get("tothigh")

    def clean_num(v: Any) -> Optional[str]:
        if v in (None, ""):
            return None
        return str(v).strip()

    bedlow = clean_num(bedlow)
    bedhigh = clean_num(bedhigh)
    totlow = clean_num(totlow)
    tothigh = clean_num(tothigh)

    parts: List[str] = []

    if bedlow and bedhigh:
        if bedlow == bedhigh:
            parts.append(f"${bedlow}/bed")
        else:
            parts.append(f"${bedlow}-${bedhigh}/bed")
    elif bedlow:
        parts.append(f"${bedlow}/bed")
    elif bedhigh:
        parts.append(f"${bedhigh}/bed")

    if totlow and tothigh:
        if totlow == tothigh:
            parts.append(f"${totlow} total")
        else:
            parts.append(f"${totlow}-${tothigh} total")
    elif totlow:
        parts.append(f"${totlow} total")
    elif tothigh:
        parts.append(f"${tothigh} total")

    if parts:
        return " | ".join(parts)

    if parsed_prices:
        if len(parsed_prices) == 1:
            return f"${parsed_prices[0]:.0f}"
        return f"${min(parsed_prices):.0f}-${max(parsed_prices):.0f}"

    return None

def extract_image_urls(payload: Dict[str, Any]) -> List[str]:
    urls: List[str] = []

    photos = payload.get("photos") or []
    for photo in photos:
        if not isinstance(photo, dict):
            continue

        img_id = photo.get("img")
        if img_id:
            urls.append(f"{GREENST_BASE_URL}/img/{img_id}")

        url = photo.get("url") or photo.get("src")
        if url:
            abs_url = absolutize(url)
            if abs_url:
                urls.append(abs_url)

    deduped: List[str] = []
    seen = set()
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    return deduped

class GreenStreetPropertiesSpider(scrapy.Spider):
    name = "greenst_properties"
    allowed_domains = ["www.greenstrealty.com", "greenstrealty.com"]
    start_urls = GREENST_PROPERTIES_URLS

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) "
            "Gecko/20100101 Firefox/148.0"
        ),
        "LOG_LEVEL": "INFO",
    }

    def parse(self, response: Response):
        now = datetime.now(timezone.utc)

        scripts = response.css("script.property-info-json::text").getall()
        seen_urls = set()

        for raw in scripts:
            raw = raw.strip()
            if not raw:
                continue

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            apartments_url = absolutize(payload.get("url")) or response.url
            if apartments_url in seen_urls:
                continue
            seen_urls.add(apartments_url)

            title = clean_text(payload.get("address_1")) or clean_text(payload.get("slug")) or clean_text(payload.get("title"))
            address_parts = [
                clean_text(payload.get("address_1")),
                clean_text(payload.get("address_2")),
                clean_text(payload.get("city")),
                clean_text(payload.get("state")),
                clean_text(payload.get("zip")),
            ]
            address = clean_text(", ".join([p for p in address_parts if p]))

            fplans = payload.get("fplans") or []
            prices, availability_raw, bedrooms, bathrooms, sqft = extract_floorplan_summary(fplans)

            price_raw = build_price_raw(payload, prices)
            flags = derive_flags_from_text(payload)
            image_urls = extract_image_urls(payload)
            primary_image = image_urls[0] if image_urls else None

            features: List[str] = []

            subtitle = clean_text(payload.get("subtitle"))
            if subtitle:
                features.append(subtitle)

            property_area = clean_text(payload.get("property_area"))
            if property_area:
                features.append(f"Area: {property_area}")

            property_type = clean_text(payload.get("type_of_property"))
            if property_type:
                features.append(f"Type: {property_type}")

            if payload.get("roommate_match") == "1":
                features.append("Roommate match available")

            additional = {
                "features": features,
                "source_page": response.url,
                "greenstreet_id": payload.get("id"),
                "subtitle": subtitle,
                "slug": payload.get("slug"),
                "property_area": property_area,
                "type_of_property": property_type,
                "featured": payload.get("featured"),
                "roommate_match": payload.get("roommate_match"),
                "prices_structured": payload.get("prices"),
                "fplans": fplans,
                "photos": payload.get("photos"),
            }
            record = ApartmentRecord(
                leasing_company_name="Green Street Realty",
                leasing_company_url=GREENST_BASE_URL,
                apartments_url=apartments_url,
                name=title,
                address=address,
                prices=prices,
                price_raw=price_raw,
                availability_raw=availability_raw,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                sqft_living=sqft,
                apartments_images=primary_image,
                image_urls=image_urls or None,
                additional_amenities=additional,
                date_scraped=now,
                pets=flags["pets"],
                furnished=flags["furnished"],
                washer_dryer_in_unit=flags["washer_dryer_in_unit"],
                washer_dryer_out_unit=flags["washer_dryer_out_unit"],
                internet=flags["internet"],
                housing_type=clean_text(payload.get("type_of_property")),
            )

            yield asdict(record)

def run_greenst_scrape(
    *,
    output_jsonl_path: Optional[str] = None,
    log_level: str = "INFO",
) -> None:
    settings: Dict[str, Any] = {"LOG_LEVEL": log_level}

    if output_jsonl_path:
        settings["FEEDS"] = {
            output_jsonl_path: {"format": "jsonlines", "encoding": "utf8", "overwrite": True}
        }

    process = CrawlerProcess(settings=settings)
    process.crawl(GreenStreetPropertiesSpider)
    process.start()