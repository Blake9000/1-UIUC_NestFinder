from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Iterable, Optional, Dict, Any, List, Tuple

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.http import Response


GREENST_BASE_URL = "https://www.greenstrealty.com"
GREENST_PROPERTIES_URL = "https://www.greenstrealty.com/properties"

@dataclass
class ApartmentRecord:
    leasing_company_name: str
    leasing_company_url: str

    apartments_url: str
    name: Optional[str] = None
    address: Optional[str] = None

    price_raw: Optional[str] = None
    availability_raw: Optional[str] = None

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

    additional_amenities: Optional[Dict[str, Any]] = None

    date_posted: Optional[datetime] = None
    date_scraped: Optional[datetime] = None


_price_money_re = re.compile(r"\$[\d,]+(?:\.\d+)?")
_bed_count_re = re.compile(r"\b(\d+)\s*Bed\b", re.IGNORECASE)
_bath_count_re = re.compile(r"\b(\d+(?:\.\d+)?)\s*Bath\b", re.IGNORECASE)

def absolutize(url: str) -> str:
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
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def parse_beds_baths_from_row_text(text: str) -> Tuple[Optional[int], Optional[float]]:
    beds = None
    baths = None

    m = re.search(r"Beds\s*:\s*(\d+)", text, flags=re.IGNORECASE)
    if m:
        beds = int(m.group(1))

    m = re.search(r"Baths?\s*:\s*(\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if m:
        try:
            baths = float(m.group(1))
        except ValueError:
            baths = None

    return beds, baths


def parse_sqft_from_row_text(text: str) -> Optional[int]:
    m = re.search(r"Sq\s*Ft\s*:\s*([\d,]+)", text, flags=re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    try:
        return int(raw)
    except ValueError:
        return None


def extract_lightbox_image_urls(response: Response) -> List[str]:
    urls: List[str] = []

    for script_text in response.css("a.w-lightbox script.w-json::text").getall():
        script_text = script_text.strip()
        if not script_text:
            continue
        try:
            payload = json.loads(script_text)
        except json.JSONDecodeError:
            continue

        items = payload.get("items") or []
        for it in items:
            u = it.get("url")
            if u:
                urls.append(absolutize(u))

    seen = set()
    deduped = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def extract_property_features(response: Response) -> List[str]:
    features = response.css(".prop-profile-features .prop-profile-html li *::text").getall()
    joined = []
    for li in response.css(".prop-profile-features .prop-profile-html li"):
        t = clean_text(" ".join(li.css("::text").getall()))
        if t:
            joined.append(t)
    return joined


def derive_flags_from_features(features: List[str]) -> Dict[str, Any]:
    blob = " ".join(f.lower() for f in features)

    out: Dict[str, Any] = {
        "pets": None,
        "furnished": None,
        "washer_dryer_in_unit": None,
        "washer_dryer_out_unit": None,
        "internet": None,
    }

    return out


class GreenStreetPropertiesSpider(scrapy.Spider):
    name = "greenst_properties"
    allowed_domains = ["www.greenstrealty.com", "greenstrealty.com"]
    start_urls = [GREENST_PROPERTIES_URL]

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": "NestFinderBot/0.1 (+local dev)",
        "LOG_LEVEL": "INFO",
    }

    def parse(self, response: Response):
        hrefs = response.css("a::attr(href)").getall()
        profile_links = []

        for href in hrefs:
            print(href)
            if not href:
                continue
            if "/properties/profile/" in href:
                profile_links.append(absolutize(href))

        seen = set()
        for url in profile_links:
            if url in seen:
                continue
            seen.add(url)
            yield response.follow(url, callback=self.parse_property)


    def parse_property(self, response: Response):
        now = datetime.now(timezone.utc)

        title = clean_text(response.css('meta[property="og:title"]::attr(content)').get())
        if not title:
            title = clean_text(response.css("title::text").get())

        address = title

        image_urls = extract_lightbox_image_urls(response)
        primary_image = image_urls[0] if image_urls else None

        info_texts: List[str] = []
        for row in response.css(".prop-profile-info-row"):
            t = clean_text(" ".join(row.css("::text").getall()))
            if t:
                info_texts.append(t)

        for row in response.css(".prop-profile-mobile-info-data"):
            t = clean_text(" ".join(row.css("::text").getall()))
            if t:
                info_texts.append(t)

        best_row = None
        for t in info_texts:
            if "Price" in t and "Availability" in t:
                best_row = t
                break

        bedrooms = None
        bathrooms = None
        sqft = None
        price_raw = None
        availability_raw = None

        if best_row:
            bedrooms, bathrooms = parse_beds_baths_from_row_text(best_row)
            sqft = parse_sqft_from_row_text(best_row)

            m = re.search(r"Price\s*:\s*(.+?)(?:Availability\s*:|$)", best_row, flags=re.IGNORECASE)
            if m:
                price_raw = clean_text(m.group(1))

            m = re.search(r"Availability\s*:\s*(.+)$", best_row, flags=re.IGNORECASE)
            if m:
                availability_raw = clean_text(m.group(1))

        features = extract_property_features(response)
        flags = derive_flags_from_features(features)

        record = ApartmentRecord(
            leasing_company_name="Green Street Realty",
            leasing_company_url=GREENST_BASE_URL,
            apartments_url=response.url,
            name=title,
            address=address,
            price_raw=price_raw,
            availability_raw=availability_raw,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            sqft_living=sqft,
            apartments_images=primary_image,
            image_urls=image_urls or None,
            additional_amenities={"features": features} if features else None,
            date_scraped=now,
            pets=flags["pets"],
            furnished=flags["furnished"],
            washer_dryer_in_unit=flags["washer_dryer_in_unit"],
            washer_dryer_out_unit=flags["washer_dryer_out_unit"],
            internet=flags["internet"],
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