import json
import re
import threading
from typing import Any

_EMBED_MODEL = None
_GEN_MODEL = None
_GEN_TOKENIZER = None
_INDEX_CACHE = None
_TORCH = None
_LOCK = threading.Lock()

EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-large-instruct"
GEN_MODEL_NAME = "HuggingFaceTB/SmolLM2-360M-Instruct"
DEVICE = "cpu"
EMBED_BATCH_SIZE = 8
RETRIEVE_TOP_K = 8
FINAL_TOP_K = 3
MAX_INPUT_TOKENS = 1200


def _import_local_ml_dependencies():
    global _TORCH
    try:
        import torch
        from sentence_transformers import SentenceTransformer
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as exc:
        raise RuntimeError(
            "Local RAG dependencies could not be loaded. "
            "For CPU-only Windows environments, reinstall a CPU-only build of PyTorch, then reinstall "
            "transformers and sentence-transformers. Original error: "
            f"{exc}"
        ) from exc

    _TORCH = torch
    return torch, SentenceTransformer, AutoModelForCausalLM, AutoTokenizer


def load_local_rag_models():
    global _EMBED_MODEL, _GEN_MODEL, _GEN_TOKENIZER

    if _EMBED_MODEL is not None and _GEN_MODEL is not None and _GEN_TOKENIZER is not None:
        return _EMBED_MODEL, _GEN_MODEL, _GEN_TOKENIZER

    with _LOCK:
        if _EMBED_MODEL is not None and _GEN_MODEL is not None and _GEN_TOKENIZER is not None:
            return _EMBED_MODEL, _GEN_MODEL, _GEN_TOKENIZER

        torch, SentenceTransformer, AutoModelForCausalLM, AutoTokenizer = _import_local_ml_dependencies()

        if _EMBED_MODEL is None:
            _EMBED_MODEL = SentenceTransformer(
                EMBEDDING_MODEL_NAME,
                trust_remote_code=True,
                device=DEVICE,
            )

        if _GEN_TOKENIZER is None:
            _GEN_TOKENIZER = AutoTokenizer.from_pretrained(GEN_MODEL_NAME)
            if _GEN_TOKENIZER.pad_token_id is None:
                _GEN_TOKENIZER.pad_token = _GEN_TOKENIZER.eos_token

        if _GEN_MODEL is None:
            _GEN_MODEL = AutoModelForCausalLM.from_pretrained(GEN_MODEL_NAME)
            _GEN_MODEL.to(DEVICE)
            _GEN_MODEL.eval()
            torch.set_grad_enabled(False)

    return _EMBED_MODEL, _GEN_MODEL, _GEN_TOKENIZER


def build_listing_document(apartment: dict[str, Any]) -> str:
    prices = apartment.get("prices") or []
    price_min = apartment.get("price_min")
    price_max = apartment.get("price_max")

    price_text = "Price unknown"
    if price_min is not None and price_max is not None:
        if price_min == price_max:
            price_text = f"${price_min:.0f}"
        else:
            price_text = f"${price_min:.0f} to ${price_max:.0f}"
    elif prices:
        try:
            low = min(float(x) for x in prices)
            high = max(float(x) for x in prices)
            price_text = f"${low:.0f}" if low == high else f"${low:.0f} to ${high:.0f}"
        except Exception:
            pass

    feature_lines = [
        f"Apartment ID: {apartment.get('id')}",
        f"Name: {apartment.get('name') or 'Unknown'}",
        f"Address: {apartment.get('address') or 'Unknown'}",
        f"Leasing company: {apartment.get('leasing_company') or 'Unknown'}",
        f"Price: {price_text}",
        f"Bedrooms: {apartment.get('bedrooms')}",
        f"Bathrooms: {apartment.get('bathrooms')}",
        f"Square feet: {apartment.get('sqft_living')}",
        f"Housing type: {apartment.get('housing_type') or 'Unknown'}",
        f"Pets allowed: {apartment.get('pets')}",
        f"Furnished: {apartment.get('furnished')}",
        f"In-unit washer/dryer: {apartment.get('washer_dryer_in_unit')}",
        f"Shared washer/dryer: {apartment.get('washer_dryer_out_unit')}",
        f"Internet: {apartment.get('internet') or 'Unknown'}",
        f"Amenities: {apartment.get('amenities_text') or 'None listed'}",
    ]

    additional_amenities = apartment.get("additional_amenities") or {}
    if additional_amenities:
        feature_lines.append(f"Additional amenities data: {json.dumps(additional_amenities, ensure_ascii=False)}")

    return "\n".join(str(line) for line in feature_lines)


def build_index_signature(apartments: list[dict[str, Any]]) -> tuple:
    signature_rows = []
    for apartment in apartments:
        signature_rows.append(
            (
                apartment.get("id"),
                apartment.get("price_min"),
                apartment.get("price_max"),
                apartment.get("bedrooms"),
                apartment.get("bathrooms"),
                apartment.get("sqft_living"),
                apartment.get("pets"),
                apartment.get("furnished"),
                apartment.get("washer_dryer_in_unit"),
                apartment.get("washer_dryer_out_unit"),
                apartment.get("housing_type"),
                apartment.get("internet"),
                apartment.get("amenities_text"),
            )
        )
    return tuple(signature_rows)


def format_query_for_embedding(query: str) -> str:
    instruction = "Retrieve apartment listings that best satisfy the renter request."
    return f"Instruct: {instruction}\nQuery: {query.strip()}"


def format_passage_for_embedding(text: str) -> str:
    return text.strip()


def build_or_get_index(apartments: list[dict[str, Any]]):
    global _INDEX_CACHE

    embed_model, _, _ = load_local_rag_models()
    signature = build_index_signature(apartments)

    if _INDEX_CACHE is not None and _INDEX_CACHE["signature"] == signature:
        return _INDEX_CACHE

    docs = [build_listing_document(apartment) for apartment in apartments]
    ids = [apartment.get("id") for apartment in apartments]

    embeddings = embed_model.encode(
        [format_passage_for_embedding(doc) for doc in docs],
        batch_size=EMBED_BATCH_SIZE,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    _INDEX_CACHE = {
        "signature": signature,
        "ids": ids,
        "docs": docs,
        "embeddings": embeddings,
        "apartments": apartments,
    }
    return _INDEX_CACHE


def retrieve_candidates(user_query: str, apartments: list[dict[str, Any]], top_k: int = RETRIEVE_TOP_K) -> list[dict[str, Any]]:
    index_data = build_or_get_index(apartments)
    embed_model, _, _ = load_local_rag_models()

    query_embedding = embed_model.encode(
        [format_query_for_embedding(user_query)],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]

    scores = index_data["embeddings"] @ query_embedding
    ranked_indices = sorted(range(len(scores)), key=lambda i: float(scores[i]), reverse=True)
    ranked_indices = ranked_indices[: min(top_k, len(apartments))]

    results = []
    for idx in ranked_indices:
        apartment = index_data["apartments"][idx]
        results.append(
            {
                "score": float(scores[idx]),
                "apartment": apartment,
                "document": index_data["docs"][idx],
            }
        )
    return results


def build_rag_ranking_prompt(user_query: str, candidates: list[dict[str, Any]]) -> str:
    context_blocks = []
    for rank, item in enumerate(candidates, start=1):
        context_blocks.append(
            f"Candidate {rank}\n"
            f"Retrieval score: {item['score']:.4f}\n"
            f"{item['document']}"
        )

    context = "\n\n---\n\n".join(context_blocks)

    return f"""
Rank the apartment candidates for this renter request.

User request:
{user_query}

Retrieved apartment candidates:
{context}

Return only JSON in this exact format:
{{"top_3":[id1,id2,id3]}}

Rules:
- Return exactly 3 apartment IDs.
- Best match first.
- Only use apartment IDs shown in the retrieved candidates.
- Prefer concrete constraints such as price, pets, bedrooms, bathrooms, furnished status, laundry, square footage, and amenities.
- Do not invent facts.
- No explanation.
""".strip()


def generate_small_model_response(prompt: str, max_new_tokens: int = 64) -> str:
    torch, _, _, _ = _import_local_ml_dependencies()
    _, gen_model, gen_tokenizer = load_local_rag_models()

    messages = [
        {"role": "system", "content": "You rank apartment listings and return strict JSON."},
        {"role": "user", "content": prompt},
    ]

    input_text = gen_tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = gen_tokenizer(
        input_text,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_INPUT_TOKENS,
    )
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

    with torch.inference_mode():
        output_ids = gen_model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=gen_tokenizer.pad_token_id,
            eos_token_id=gen_tokenizer.eos_token_id,
        )

    generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]
    return gen_tokenizer.decode(generated_ids, skip_special_tokens=True).strip()


def rank_apartments_with_local_rag(user_query: str, apartments: list[dict[str, Any]]) -> list[int]:
    candidates = retrieve_candidates(user_query, apartments, top_k=RETRIEVE_TOP_K)
    if not candidates:
        return [apartment["id"] for apartment in apartments[:FINAL_TOP_K] if apartment.get("id") is not None]

    prompt = build_rag_ranking_prompt(user_query, candidates)

    try:
        raw_response = generate_small_model_response(prompt)
        top_ids = extract_top_ids(raw_response, [item["apartment"] for item in candidates])
        if top_ids:
            return top_ids[:FINAL_TOP_K]
    except Exception:
        pass

    fallback_ids = []
    for item in candidates:
        apartment_id = item["apartment"].get("id")
        if apartment_id is not None and apartment_id not in fallback_ids:
            fallback_ids.append(apartment_id)
        if len(fallback_ids) == FINAL_TOP_K:
            break
    return fallback_ids


def extract_top_ids(raw_response: str, apartments: list[dict[str, Any]]) -> list[int]:
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
        json_match = re.search(r"\{.*\}", raw_response or "", re.DOTALL)
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

    cleaned = []
    for num in re.findall(r"\d+", raw_response or ""):
        apartment_id = int(num)
        if apartment_id in valid_ids and apartment_id not in cleaned:
            cleaned.append(apartment_id)
        if len(cleaned) == 3:
            return cleaned

    return [apartment["id"] for apartment in apartments[:3] if apartment.get("id") is not None]
