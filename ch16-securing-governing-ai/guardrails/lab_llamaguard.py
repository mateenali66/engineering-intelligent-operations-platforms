"""VALIDATION-ONLY (production output hazard classifier): Meta Llama Guard 4.

Llama Guard 4 is a 12B dense multimodal safety classifier (meta-llama/Llama-Guard-4-12B)
that scores text against the MLCommons hazard taxonomy (up to S1-S14, configurable
at inference). Meta states it needs a single GPU with about 24 GB of VRAM, so a CPU
CI runner cannot run it: this is the same GPU split as Chapter 11's vLLM path. The
rules-based hazard_check() in detectors.py stands in for it in the deterministic
gate; this is the production upgrade. py_compile-checked only.
"""

from __future__ import annotations


def llama_guard_classify(text: str) -> str:  # pragma: no cover - validation-only
    """Return 'safe' or 'unsafe\\nS<n>' from Llama Guard 4. Needs ~24 GB GPU.

        from transformers import pipeline
        guard = pipeline("text-generation", model="meta-llama/Llama-Guard-4-12B")
        # format the response in the Llama Guard chat template, read the verdict

    The hazard categories are user-configurable at inference, so a deployment
    enables the subset of S1-S14 it cares about. Not run in CI: 12B needs a GPU.
    """
    raise NotImplementedError("Llama Guard 4 is validation-only; see docstring")
