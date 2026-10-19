"""Fixed settings for the Bonsai 2 test. Everything here is frozen by PREREG.md before the main run."""
import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITEMS_DIR = os.path.join(ROOT, "items")
RESULTS_DIR = os.path.join(ROOT, "results")
MODELS_DIR = os.path.expanduser("~/models/bonsai2-test")
# All three arms run on the same binary: the PrismML llama.cpp fork (the only runtime that loads PTQ1_0).
SERVER_BIN = os.path.join(ROOT, "bin", "llama-server")
PYTHON_FOR_TESTS = "/opt/homebrew/bin/python3.12"

SYSTEM_PROMPT = "You are a helpful assistant"
CONTEXT = 32768
PORT = 8791

QWEN_SAMPLER = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}

ARMS = {
    # Vendor's own "4-bit" comparator: 85.18 avg vs 86.32 FP16 vs 84.78 Bonsai 2 on the model card.
    "A": {
        "label": "Qwen3.8 27B UD-Q4_K_XL (17.56 GB)",
        "file": "Qwen3.8-27B-UD-Q4_K_XL.gguf",
        "repo": "unsloth/Qwen3.8-27B-GGUF",
        "sha256": "3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e",
        "sampler": QWEN_SAMPLER,
        "effort_field": True,
    },
    "B": {
        "label": "Bonsai 2 27B PTQ1_0 (5.95 GB)",
        "file": "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
        "repo": "prism-ml/Ternary-Bonsai-2-27B-gguf",
        "sha256": "53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3",
        "sampler": QWEN_SAMPLER,
        "effort_field": True,
    },
    # Equal-memory control: closest 4-bit Gemma 4 12B file to 5.95 GB. Its own card's sampler; thinking on.
    "C": {
        "label": "Gemma 4 12B IQ4_XS (6.38 GB)",
        "file": "gemma-4-12b-it-IQ4_XS.gguf",
        "repo": "unsloth/gemma-4-12b-it-GGUF",
        "sha256": "b0037d0e0de0290177045ca214b2a0fb1079d18bde57842b3ca32f5b0cd76774",
        "sampler": {"temperature": 1.0, "top_p": 0.95, "top_k": 64},
        "effort_field": False,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
    },
}

MAX_TOKENS = {"medium": 8192, "xhigh": 16384}
MAX_TOOL_TURNS = 20  # references need up to 8 calls; 12 left too little room for exploratory reads
CODE_TIMEOUT_S = 10
REQUEST_TIMEOUT_S = 3 * 3600

SEEDS = {"main": 1001, "noise": 2002, "xhigh": 1001, "pilot": 7}
FAMILIES = ("reasoning", "coding", "tools")
NOISE_PER_FAMILY = {"reasoning": 13, "coding": 13, "tools": 14}
XHIGH_PER_FAMILY = 4
FALLBACK_PER_FAMILY = 30  # the 90-item fallback if the pilot shows the full run is too slow


def stable_order(ids):
    """Fixed pseudo-random order that does not depend on anything run-time: sort by sha256 of the id."""
    return sorted(ids, key=lambda i: hashlib.sha256(i.encode()).hexdigest())
