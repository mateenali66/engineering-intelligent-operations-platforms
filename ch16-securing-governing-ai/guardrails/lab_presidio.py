"""VALIDATION (production PII path): Microsoft Presidio analyze + anonymize.

Presidio runs fully local on CPU with no API key and installs without torch, so
it CAN run in CI on Python 3.12 (presidio-analyzer caps at <3.14). It is kept in
an optional local run rather than the deterministic gate because its small-model
NER is probabilistic: in a measured run en_core_web_sm mislabeled an SSN as
ORGANIZATION, which is itself the lesson that PII detection is heuristic. The
deterministic regex scrub in detectors.py is the reliable CI default; this is the
production upgrade. Run: pip install -r requirements-presidio.txt plus the
en_core_web_sm wheel (use the wheel URL, not `spacy download`).
"""

from __future__ import annotations


def presidio_scrub(text: str) -> tuple[str, list[str]]:  # pragma: no cover - optional job
    """Detect and anonymize PII with Presidio. Returns (anonymized, entity_types).

        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        results = AnalyzerEngine().analyze(text=text, language="en")
        out = AnonymizerEngine().anonymize(text=text, analyzer_results=results)
        return out.text, sorted({r.entity_type for r in results})

    Presidio's email and phone hits come from deterministic checksum/pattern
    recognizers that do not need the NLP model; the PERSON/SSN spans come from the
    NER model and are the unreliable part. Assert presence, not exact spans.
    """
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine

    results = AnalyzerEngine().analyze(text=text, language="en")
    anonymized = AnonymizerEngine().anonymize(text=text, analyzer_results=results)
    return anonymized.text, sorted({r.entity_type for r in results})
