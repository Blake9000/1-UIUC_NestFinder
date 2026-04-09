from __future__ import annotations

import json
import pickle
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_EMBED_MODEL = None
_INDEX_CACHE = None
_LOCK = threading.Lock()

# Smaller and faster CPU-friendly embedding model.
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEVICE = "cpu"
EMBED_BATCH_SIZE = 32
RETRIEVE_TOP_K = 8
FINAL_TOP_K = 3
ALLOW_STALE_INDEX = True

CACHE_DIR = Path(__file__).resolve().parents[1] / "data"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
INDEX_CACHE_PATH = CACHE_DIR / "apartment_embedding_index.pkl"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "best", "between", "do", "for", "from",
    "get", "give", "has", "have", "i", "in", "is", "it", "me", "my", "near", "of", "on",
    "or", "please", "show", "that", "the", "to", "want", "which", "with", "within", "you",
}


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _import_sentence_transformers():
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        raise RuntimeError(
            "Local embedding dependencies could not be loaded. "
            "Install sentence-transformers and a working CPU PyTorch build. "
            f"Original error: {exc}"
        ) from exc
    return SentenceTransformer


def load_embedding_model():
    global _EMBED_MODEL

    if _EMBED_MODEL is not None:
        return _EMBED_MODEL

    with _LOCK:
        if _EMBED_MODEL is not None:
            return _EMBED_MODEL

        SentenceTransformer = _import_sentence_transformers()
        _EMBED_MODEL = SentenceTransformer(
            EMBEDDING_MODEL_NAME,
            trust_remote_code=False,
            device=DEVICE,
        )

    return _EMBED_MODEL


def build_listing_document(apartment: dict[str, Any]) -> str:
    prices = apartment.get("prices") or []
    price_min = apartment.get("price_min")
    price_max = apartment.get("price_max")

    price_text = "price unknown"
    if price_min is not None and price_max is not None:
        price_text = f"${price_min:.0f}" if price_min == price_max else f"${price_min:.0f} to ${price_max:.0f}"
    elif prices:
        try:
            low = min(float(x) for x in prices)
            high = max(float(x) for x in prices)
            price_text = f"${low:.0f}" if low == high else f"${low:.0f} to ${high:.0f}"
        except Exception:
            pass

    details = [
        f"Apartment ID {apartment.get('id')}",
        f"name {apartment.get('name') or 'unknown'}",
        f"address {apartment.get('address') or 'unknown'}",
        f"leasing company {apartment.get('leasing_company') or 'unknown'}",
        f"price {price_text}",
        f"bedrooms {apartment.get('bedrooms')}",
        f"bathrooms {apartment.get('bathrooms')}",
        f"square feet {apartment.get('sqft_living')}",
        f"housing type {apartment.get('housing_type') or 'unknown'}",
        f"pets allowed {apartment.get('pets')}",
        f"furnished {apartment.get('furnished')}",
        f"in-unit laundry {apartment.get('washer_dryer_in_unit')}",
        f"shared laundry {apartment.get('washer_dryer_out_unit')}",
        f"internet {apartment.get('internet') or 'unknown'}",
    ]

    amenities_text = apartment.get("amenities_text")
    if amenities_text:
        details.append(f"amenities {amenities_text}")

    return ". ".join(str(x) for x in details if x not in [None, ""])


def _cache_signature(apartments: list[dict[str, Any]]) -> dict[str, Any]:
    ids: list[int] = []
    newest_scrape: datetime | None = None

    for apartment in apartments:
        apartment_id = apartment.get("id")
        if apartment_id is not None:
            ids.append(int(apartment_id))
        scraped = _parse_datetime(apartment.get("date_scraped"))
        if scraped and (newest_scrape is None or scraped > newest_scrape):
            newest_scrape = scraped

    return {
        "count": len(apartments),
        "ids": tuple(sorted(ids)),
        "newest_date_scraped": newest_scrape.isoformat() if newest_scrape else None,
    }


def _build_index_from_apartments(apartments: list[dict[str, Any]]) -> dict[str, Any]:
    embed_model = load_embedding_model()
    docs = [build_listing_document(apartment) for apartment in apartments]
    ids = [apartment.get("id") for apartment in apartments]

    embeddings = embed_model.encode(
        docs,
        batch_size=EMBED_BATCH_SIZE,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "signature": _cache_signature(apartments),
        "ids": ids,
        "docs": docs,
        "embeddings": embeddings,
    }


def _load_disk_index() -> dict[str, Any] | None:
    if not INDEX_CACHE_PATH.exists():
        return None

    try:
        with INDEX_CACHE_PATH.open("rb") as fh:
            return pickle.load(fh)
    except Exception:
        return None


def _write_disk_index(index_data: dict[str, Any]) -> None:
    temp_path = INDEX_CACHE_PATH.with_suffix(".tmp")
    with temp_path.open("wb") as fh:
        pickle.dump(index_data, fh, protocol=pickle.HIGHEST_PROTOCOL)
    temp_path.replace(INDEX_CACHE_PATH)


def _get_cached_index(apartments: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, bool]:
    global _INDEX_CACHE

    current_signature = _cache_signature(apartments)

    with _LOCK:
        if _INDEX_CACHE is not None:
            is_exact = _INDEX_CACHE.get("signature") == current_signature
            if is_exact or ALLOW_STALE_INDEX:
                return _INDEX_CACHE, not is_exact

        disk_index = _load_disk_index()
        if disk_index is None:
            return None, False

        _INDEX_CACHE = disk_index
        is_exact = disk_index.get("signature") == current_signature
        if is_exact or ALLOW_STALE_INDEX:
            return _INDEX_CACHE, not is_exact
        return None, False


def refresh_apartment_index(apartments: list[dict[str, Any]]) -> dict[str, Any]:
    global _INDEX_CACHE
    with _LOCK:
        index_data = _build_index_from_apartments(apartments)
        _write_disk_index(index_data)
        _INDEX_CACHE = index_data
        return index_data


def get_index_status(apartments: list[dict[str, Any]]) -> dict[str, Any]:
    index_data, is_stale = _get_cached_index(apartments)
    return {
        "cache_path": str(INDEX_CACHE_PATH),
        "exists": index_data is not None,
        "stale": bool(is_stale),
        "signature": index_data.get("signature") if index_data else None,
        "created_at": index_data.get("created_at") if index_data else None,
    }


def format_query_for_embedding(query: str) -> str:
    return query.strip()


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS and len(t) > 1]


def _parse_budget(query: str) -> tuple[float | None, float | None]:
    lowered = query.lower()
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", lowered)]
    if not nums:
        return None, None

    between = re.search(r"between\s+\$?(\d+(?:\.\d+)?)\s+(?:and|to)\s+\$?(\d+(?:\.\d+)?)", lowered)
    if between:
        return float(between.group(1)), float(between.group(2))

    under = re.search(r"(?:under|below|less than|max(?:imum)?|up to)\s+\$?(\d+(?:\.\d+)?)", lowered)
    if under:
        return None, float(under.group(1))

    over = re.search(r"(?:over|above|more than|at least|min(?:imum)?)\s+\$?(\d+(?:\.\d+)?)", lowered)
    if over:
        return float(over.group(1)), None

    if len(nums) >= 2:
        return min(nums[0], nums[1]), max(nums[0], nums[1])

    return None, None


def _heuristic_score(user_query: str, apartment: dict[str, Any], document: str | None = None) -> float:
    query = user_query.lower()
    doc = (document or build_listing_document(apartment)).lower()
    score = 0.0

    terms = _tokenize(user_query)
    score += sum(1.0 for term in terms if term in doc)

    bedrooms = apartment.get("bedrooms")
    bathrooms = apartment.get("bathrooms")
    pets = apartment.get("pets")
    furnished = apartment.get("furnished")
    laundry_in = apartment.get("washer_dryer_in_unit")
    laundry_shared = apartment.get("washer_dryer_out_unit")
    sqft = apartment.get("sqft_living")
    price_min = apartment.get("price_min")
    price_max = apartment.get("price_max")

    bed_match = re.search(r"(\d+)\s*(?:bed|bedroom)", query)
    if bed_match and bedrooms is not None:
        score += 4.0 if int(bed_match.group(1)) == int(bedrooms) else -1.0

    bath_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:bath|bathroom)", query)
    if bath_match and bathrooms is not None:
        score += 4.0 if abs(float(bath_match.group(1)) - float(bathrooms)) < 0.01 else -1.0

    if any(word in query for word in ["cat", "cats", "dog", "dogs", "pet", "pets"]):
        if pets is True:
            score += 4.0
        elif pets is False:
            score -= 3.0

    if "furnished" in query:
        score += 3.0 if furnished is True else -1.0

    if any(word in query for word in ["laundry", "washer", "dryer", "in-unit", "in unit"]):
        if laundry_in is True:
            score += 3.5
        elif laundry_shared is True:
            score += 1.0

    if any(word in query for word in ["largest", "biggest", "spacious", "square feet", "sqft"]):
        if sqft:
            score += float(sqft) / 1000.0

    budget_min, budget_max = _parse_budget(query)
    if price_min is not None or price_max is not None:
        listing_low = float(price_min) if price_min is not None else float(price_max)
        listing_high = float(price_max) if price_max is not None else float(price_min)
        if budget_min is not None and listing_high >= budget_min:
            score += 1.5
        if budget_max is not None and listing_low <= budget_max:
            score += 1.5
        if budget_min is not None and budget_max is not None:
            if listing_low <= budget_max and listing_high >= budget_min:
                score += 3.0
            else:
                score -= 2.0

    if "cheapest" in query or "least expensive" in query:
        if price_min is not None:
            score += max(0.0, 5.0 - float(price_min) / 1000.0)

    if "most expensive" in query or "luxury" in query:
        if price_max is not None:
            score += float(price_max) / 1000.0

    return score


def _retrieve_from_cached_index(user_query: str, apartments: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    index_data, _is_stale = _get_cached_index(apartments)
    if index_data is None:
        return []

    embed_model = load_embedding_model()
    query_embedding = embed_model.encode(
        [format_query_for_embedding(user_query)],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]

    scores = index_data["embeddings"] @ query_embedding
    ranked_indices = sorted(range(len(scores)), key=lambda i: float(scores[i]), reverse=True)

    apartment_map = {apartment.get("id"): apartment for apartment in apartments if apartment.get("id") is not None}
    results: list[dict[str, Any]] = []

    for idx in ranked_indices:
        apartment_id = index_data["ids"][idx]
        apartment = apartment_map.get(apartment_id)
        if apartment is None:
            continue
        results.append(
            {
                "score": float(scores[idx]),
                "apartment": apartment,
                "document": index_data["docs"][idx],
            }
        )
        if len(results) >= min(top_k, len(apartments)):
            break

    return results


def _retrieve_with_heuristics(user_query: str, apartments: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    scored = []
    for apartment in apartments:
        document = build_listing_document(apartment)
        scored.append(
            {
                "score": _heuristic_score(user_query, apartment, document),
                "apartment": apartment,
                "document": document,
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: min(top_k, len(scored))]


def rank_apartments_with_local_rag(user_query: str, apartments: list[dict[str, Any]]) -> list[int]:
    candidates = _retrieve_from_cached_index(user_query, apartments, top_k=RETRIEVE_TOP_K)
    if not candidates:
        candidates = _retrieve_with_heuristics(user_query, apartments, top_k=RETRIEVE_TOP_K)

    top_ids: list[int] = []
    for item in candidates:
        apartment_id = item["apartment"].get("id")
        if apartment_id is not None and apartment_id not in top_ids:
            top_ids.append(apartment_id)
        if len(top_ids) >= FINAL_TOP_K:
            break

    if top_ids:
        return top_ids

    return [apartment["id"] for apartment in apartments[:FINAL_TOP_K] if apartment.get("id") is not None]
