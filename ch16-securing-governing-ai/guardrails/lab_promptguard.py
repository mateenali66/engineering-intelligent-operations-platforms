"""VALIDATION-ONLY (production input classifier): Meta Prompt Guard 2.

Prompt Guard 2 is a small encoder classifier (Llama-Prompt-Guard-2-86M is
mDeBERTa-base; the 22M is DeBERTa-xsmall) that labels an input BENIGN or
MALICIOUS. It runs on CPU, but the weights are gated under the Llama 4 Community
License, so a cold download needs a HuggingFace token. That makes it
validation-only in CI: the deterministic detect_injection() heuristic runs for
real in the gate; this is the production upgrade. py_compile-checked only.
"""

from __future__ import annotations


def prompt_guard_score(text: str) -> str:  # pragma: no cover - validation-only
    """Return 'BENIGN' or 'MALICIOUS' from Prompt Guard 2. Needs a gated download.

        from transformers import pipeline
        clf = pipeline("text-classification",
                       model="meta-llama/Llama-Prompt-Guard-2-86M")
        return clf(text)[0]["label"]

    Prompt Guard 2 collapsed version 1's three labels (benign/injection/jailbreak)
    to a binary BENIGN/MALICIOUS decision. Not run in CI: the download is gated.
    """
    raise NotImplementedError("Prompt Guard 2 is validation-only; see docstring")
