import torch
import threading
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

_MODEL = None
_TOKENIZER = None
_LOCK = threading.Lock()

MODEL_ID = "vhab10/llama-3-8b-merged-linear"

def load_llama():
    global _MODEL, _TOKENIZER

    if _MODEL is not None:
        return _MODEL, _TOKENIZER

    with _LOCK:
        if _MODEL is not None:
            return _MODEL, _TOKENIZER

        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True
        )

        _TOKENIZER = AutoTokenizer.from_pretrained(MODEL_ID)

        _MODEL = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            quantization_config=quant_config,
            device_map="auto",
            torch_dtype=torch.float16
        )

        return _MODEL, _TOKENIZER


def generate_llama_response(prompt: str, max_new_tokens=150) -> str:
    model, tokenizer = load_llama()

    messages = [{"role": "user", "content": prompt}]

    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        pad_token_id=tokenizer.eos_token_id,
        do_sample=False
    )

    return tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[-1]:],
        skip_special_tokens=True
    )
