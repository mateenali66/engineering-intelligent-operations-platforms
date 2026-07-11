"""The output layer: run a hazard check, block outbound-communication signals,
and redact PII the model may have emitted. This layer is real but limited: it
scores the response text, so it cannot tell that an instruction in the response
was injected by an untrusted retrieved document rather than intended by the user.
That blind spot is the teaching moment in Section 16.4. What it can do cheaply and
deterministically is check for the outbound-URL exfiltration channel, so the
markdown-image data-leak pattern does not sail through unexamined.
"""

from __future__ import annotations

from .detectors import detect_exfil, hazard_check, scrub_pii


def filter_output(response: str) -> dict:
    """Run the hazard check, block exfiltration signals, then redact PII.

    {'blocked': True, 'reason': 'hazard', ...} if a hazard category fires;
    {'blocked': True, 'reason': 'exfil', ...} if an outbound-URL / send-to /
    curl signal is present (the markdown-image exfiltration channel); else
    {'blocked': False, 'response': <pii-redacted response>}.
    """
    hazards = hazard_check(response)
    if hazards:
        return {"blocked": True, "reason": "hazard", "categories": hazards}
    exfil = detect_exfil(response)
    if exfil:
        return {"blocked": True, "reason": "exfil", "signals": exfil}
    redacted, pii = scrub_pii(response)
    return {"blocked": False, "response": redacted, "pii_redacted": pii}
