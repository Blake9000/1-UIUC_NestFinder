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
GREENST_PROPERTIES_URL = "https://www.greenstrealty.com/modules/extended/propertySearch"

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

    additional_amenities: Optional[Dict[str, Any]] = None

    date_posted: Optional[datetime] = None
    date_scraped: Optional[datetime] = None


_price_money_re = re.compile(r"\$[\d,]+(?:\.\d+)?")

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


def parse_prices_from_price_raw(price_raw: Optional[str]) -> Optional[List[float]]:
    if not price_raw:
        return None

    matches = _price_money_re.findall(price_raw)
    if not matches:
        return None

    out: List[float] = []
    for m in matches:
        n = m.replace("$", "").replace(",", "")
        try:
            out.append(float(n))
        except ValueError:
            continue

    return out or None


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
    joined = []
    for li in response.css(".prop-profile-features .prop-profile-html li"):
        t = clean_text(" ".join(li.css("::text").getall()))
        if t:
            joined.append(t)
    return joined


def derive_flags_from_features(features: List[str]) -> Dict[str, Any]:
    return {
        "pets": None,
        "furnished": None,
        "washer_dryer_in_unit": None,
        "washer_dryer_out_unit": None,
        "internet": None,
    }


def extract_price_availability_and_stats(response: Response) -> Tuple[
    Optional[str], Optional[str], Optional[int], Optional[float], Optional[int]
]:
    """
    Robust extraction that does NOT rely on a single row containing both Price + Availability.

    Returns:
      (price_raw, availability_raw, bedrooms, bathrooms, sqft_living)
    """
    price_parts: List[str] = []
    availability_parts: List[str] = []
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None

    # Prefer mobile blocks, then fallback to info rows
    blocks = list(response.css(".prop-profile-mobile-info-data"))
    if not blocks:
        blocks = list(response.css(".prop-profile-info-row"))

    for block in blocks:
        t = clean_text(" ".join(block.css("::text").getall()))
        if not t:
            continue

        # pull beds/baths/sqft opportunistically
        if bedrooms is None or bathrooms is None:
            b, ba = parse_beds_baths_from_row_text(t)
            if bedrooms is None and b is not None:
                bedrooms = b
            if bathrooms is None and ba is not None:
                bathrooms = ba

        if sqft is None:
            s = parse_sqft_from_row_text(t)
            if s is not None:
                sqft = s

        # capture price / availability
        m = re.search(r"Price\s*:\s*(.+?)(?:Availability\s*:|$)", t, flags=re.IGNORECASE)
        if m:
            pr = clean_text(m.group(1))
            if pr:
                price_parts.append(pr)

        m = re.search(r"Availability\s*:\s*(.+)$", t, flags=re.IGNORECASE)
        if m:
            av = clean_text(m.group(1))
            if av:
                availability_parts.append(av)

    # Fallback: regex over the raw HTML if CSS text extraction misses it
    if not price_parts:
        for m in re.finditer(r"Price\s*:\s*([^<\r\n]+)", response.text, flags=re.IGNORECASE):
            pr = clean_text(m.group(1))
            if pr:
                price_parts.append(pr)

    if not availability_parts:
        for m in re.finditer(r"Availability\s*:\s*([^<\r\n]+)", response.text, flags=re.IGNORECASE):
            av = clean_text(m.group(1))
            if av:
                availability_parts.append(av)

    # Deduplicate while preserving order
    def dedupe_keep_order(vals: List[str]) -> List[str]:
        seen = set()
        out = []
        for v in vals:
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out

    price_parts = dedupe_keep_order(price_parts)
    availability_parts = dedupe_keep_order(availability_parts)

    price_raw = " | ".join(price_parts) if price_parts else None
    availability_raw = " | ".join(availability_parts) if availability_parts else None

    return price_raw, availability_raw, bedrooms, bathrooms, sqft


class GreenStreetPropertiesSpider(scrapy.Spider):
    name = "greenst_properties"
    allowed_domains = ["www.greenstrealty.com", "greenstrealty.com"]
    start_urls = [GREENST_PROPERTIES_URL]

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0",
        "LOG_LEVEL": "INFO",
    }

    def parse(self, response: Response):
        hrefs = response.css("a::attr(href)").getall()
        profile_links = []

        for href in hrefs:
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

        # IMPLEMENTED: robust extraction
        price_raw, availability_raw, bedrooms, bathrooms, sqft = extract_price_availability_and_stats(response)
        prices = parse_prices_from_price_raw(price_raw)

        features = extract_property_features(response)
        flags = derive_flags_from_features(features)

        additional = {"features": features} if features else None

        record = ApartmentRecord(
            leasing_company_name="Green Street Realty",
            leasing_company_url=GREENST_BASE_URL,
            apartments_url=response.url,
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