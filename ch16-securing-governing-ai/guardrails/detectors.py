"""Deterministic detectors: the parts of the guardrail pipeline that run for real
in CI with no model and no key. Each is a heuristic, which is the honest point:
these are pattern matchers, not guarantees. The production equivalents are Meta
Prompt Guard 2 (injection), Microsoft Presidio (PII), and Meta Llama Guard 4
(hazards), all of which are probabilistic classifiers in their own right.
"""

from __future__ import annotations

import re

# Direct prompt-injection patterns. A real classifier (Prompt Guard 2) catches
# far more; these cover the obvious overrides and make the input gate testable.
_INJECTION_PATTERNS: dict[str, re.Pattern] = {
    "ignore_instructions": re.compile(
        r"\bignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+instructions?\b",
        re.IGNORECASE,
    ),
    "reveal_system_prompt": re.compile(
        r"\b(reveal|show|print|repeat|leak)\b.{0,30}\bsystem\s+prompt\b", re.IGNORECASE
    ),
    "override_role": re.compile(
        r"\byou\s+are\s+now\b|\bdisregard\b.{0,20}\b(rules|policy|guidelines)\b",
        re.IGNORECASE,
    ),
}

# PII regexes: the reliable, deterministic part of Presidio's behavior (its
# checksum/pattern recognizers), reproduced without the NLP model.
_PII_PATTERNS: dict[str, re.Pattern] = {
    "EMAIL": re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    "PHONE": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}

# External-communication signals: the third leg of the lethal trifecta.
_EXFIL_PATTERNS: dict[str, re.Pattern] = {
    "url": re.compile(r"https?://\S+", re.IGNORECASE),
    "send_to": re.compile(r"\b(send|email|post|exfiltrate|upload)\b.{0,20}\bto\b", re.IGNORECASE),
    "curl": re.compile(r"\bcurl\b|\bwget\b", re.IGNORECASE),
}

# Rules-based stand-in for Llama Guard 4's MLCommons hazard taxonomy (S1-S14).
# Production swaps this for the 12B model or a managed content-safety API.
_HAZARD_PATTERNS: dict[str, re.Pattern] = {
    "S9_weapons": re.compile(r"\b(build|make|synthesize)\b.{0,30}\b(bomb|explosive|nerve agent)\b", re.IGNORECASE),
    "S2_cyber": re.compile(r"\b(write|generate)\b.{0,20}\b(ransomware|keylogger|malware)\b", re.IGNORECASE),
}


def detect_injection(text: str) -> list[str]:
    """Return the names of injection patterns matched (empty list means clean)."""
    return [name for name, pat in _INJECTION_PATTERNS.items() if pat.search(text)]


def scrub_pii(text: str) -> tuple[str, list[str]]:
    """Redact email, phone, and SSN spans. Returns (redacted_text, labels_found)."""
    labels: list[str] = []
    redacted = text
    for label, pat in _PII_PATTERNS.items():
        if pat.search(redacted):
            labels.append(label)
            redacted = pat.sub(f"<{label}>", redacted)
    return redacted, labels


def detect_exfil(text: str) -> list[str]:
    """Return external-communication signals found in the text."""
    return [name for name, pat in _EXFIL_PATTERNS.items() if pat.search(text)]


def hazard_check(text: str) -> list[str]:
    """Rules-based hazard categories matched (stand-in for Llama Guard 4)."""
    return [name for name, pat in _HAZARD_PATTERNS.items() if pat.search(text)]
