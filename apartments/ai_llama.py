import json
import re
import threading
import torch

from transformers import AutoTokenizer, AutoModelForCausalLM

_MODEL = None
_TOKENIZER = None
_LOCK = threading.Lock()

MODEL_ID = "vhab10/llama-3-8b-merged-linear"


def detect_device():
    print(f"[LLAMA] torch version: {torch.__version__}")
    print(f"[LLAMA] torch cuda build: {torch.version.cuda}")
    print(f"[LLAMA] cuda available: {torch.cuda.is_available()}")
    print(f"[LLAMA] cuda device count: {torch.cuda.device_count()}")

    if torch.cuda.is_available():
        print(f"[LLAMA] cuda device 0: {torch.cuda.get_device_name(0)}")
        return "cuda"

    return "cpu"


def load_llama():
    global _MODEL, _TOKENIZER

    if _MODEL is not None:
        return _MODEL, _TOKENIZER

    with _LOCK:
        if _MODEL is not None:
            return _MODEL, _TOKENIZER

        device = detect_device()
        _TOKENIZER = AutoTokenizer.from_pretrained(MODEL_ID)

        if device == "cuda":
            try:
                from transformers import BitsAndBytesConfig

                quant_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True
                )

                print("[LLAMA] Trying 4-bit quantized GPU load")

                _MODEL = AutoModelForCausalLM.from_pretrained(
                    MODEL_ID,
                    quantization_config=quant_config,
                    device_map="auto",
                    dtype=torch.float16,
                    low_cpu_mem_usage=True
                )

                _MODEL.eval()
                torch.set_grad_enabled(False)

                print("[LLAMA] Quantized GPU load succeeded")
                return _MODEL, _TOKENIZER

            except Exception as e:
                print(f"[LLAMA] Quantized GPU load failed: {e}")
                raise RuntimeError(
                    "Local model could not be loaded on GPU. "
                    "Use API mode or a smaller local model."
                ) from e

        raise RuntimeError("CUDA is not available for the local model.")


def get_model_device(model):
    try:
        return model.get_input_embeddings().weight.device
    except Exception:
        try:
            return next(model.parameters()).device
        except StopIteration:
            return torch.device("cpu")


def generate_llama_response(prompt: str, max_new_tokens=48) -> str:
    model, tokenizer = load_llama()

    messages = [{"role": "user", "content": prompt}]

    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    )

    model_device = get_model_device(model)
    inputs = {k: v.to(model_device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            pad_token_id=tokenizer.eos_token_id,
            do_sample=False,
            use_cache=True
        )

    return tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[-1]:],
        skip_special_tokens=True
    )


def rank_apartments_with_llama(user_query: str, apartments: list[dict]) -> list[int]:
    compact_apartments = apartments
    prompt = build_ranking_prompt(user_query, compact_apartments)
    raw_response = generate_llama_response(prompt, max_new_tokens=48)
    return extract_top_ids(raw_response, compact_apartments)


def build_ranking_prompt(user_query: str, apartments: list[dict]) -> str:
    apartment_lines = []

    for apartment in apartments:
        compact = {
            "id": apartment["id"],
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


def extract_top_ids(raw_response: str, apartments: list[dict]) -> list[int]:
    valid_ids = {apartment["id"] for apartment in apartments}

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

    numbers = re.findall(r"\d+", raw_response)
    cleaned = []
    for num in numbers:
        apartment_id = int(num)
        if apartment_id in valid_ids and apartment_id not in cleaned:
            cleaned.append(apartment_id)

    if len(cleaned) >= 3:
        return cleaned[:3]

    return [apartment["id"] for apartment in apartments[:3]]