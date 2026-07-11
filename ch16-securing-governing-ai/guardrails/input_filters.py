"""The input layer: block a direct injection in the user prompt, then scrub PII
from it before it reaches the model. Note what this layer does NOT see: the
retrieved document. Input filtering scans the user's prompt, not arbitrary
content the system later pulls in, which is exactly why indirect injection
slips past it (Chapter 16, Section 16.4).
"""

from __future__ import annotations

from .detectors import detect_injection, scrub_pii


def filter_input(prompt: str) -> dict:
    """Return a verdict for the user prompt.

    {'blocked': True, 'reason': ...} if a direct injection is detected, else
    {'blocked': False, 'clean_prompt': <pii-scrubbed prompt>, 'pii': [...]}.
    """
    hits = detect_injection(prompt)
    if hits:
        return {"blocked": True, "reason": "prompt_injection", "patterns": hits}
    clean, pii = scrub_pii(prompt)
    return {"blocked": False, "clean_prompt": clean, "pii": pii}
