"""The layered guardrail proxy: input defenses, an architectural containment
layer, a stubbed LLM, then output defenses. The containment layer is the chapter's
load-bearing control: it breaks the lethal trifecta (access to private data,
exposure to untrusted content, and the ability to communicate externally) by
refusing to let an external tool run whenever untrusted content is in the request.

Threat model: in a public-facing deployment there are two untrusted content
sources, not one. A retrieved document is the obvious one. The USER is the other:
a malicious authenticated user can type the attacker-controlled instruction
straight into the prompt, so gating only on the presence of a retrieved document
lets a malicious-user-plus-tool request complete the trifecta with no RAG at all.

Trust is decided on the server, never read from the request. The caller presents
a bearer token; the proxy resolves it to a principal from server-side config and
treats the user as trusted only if that principal is on a server-side allowlist
of internal services. A request body that tries to carry its own trust flag is
rejected, and an unknown or forged token is simply anonymous, so untrusted.
Production verifies an OIDC token or an mTLS identity at the gateway instead of
a static key table; the rule is the same: identity decides trust, input does not.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Depends, FastAPI, Header
from pydantic import BaseModel, ConfigDict

from .input_filters import filter_input
from .output_filters import filter_output

app = FastAPI(title="Guardrail Proxy")


def stub_llm(context: str) -> str:
    """Deterministic stand-in for the LLM, so the pipeline runs with no key."""
    return f"ECHO: {context[:80]}"


# Server-owned: the principals allowed to relax the user leg of the trifecta.
TRUSTED_PRINCIPALS = frozenset({"svc:runbook-bot"})


class ChatRequest(BaseModel):
    # Unknown fields are rejected, so a client cannot smuggle in a trust flag.
    model_config = ConfigDict(extra="forbid")

    prompt: str
    retrieved: str = ""           # untrusted retrieved document (RAG context)
    allow_external_tool: bool = False


def _api_keys() -> dict[str, str]:
    """Token-to-principal table from server config: 'tok1=svc:a,tok2=svc:b'."""
    raw = os.environ.get("GUARDRAIL_API_KEYS", "")
    pairs = (item.split("=", 1) for item in raw.split(",") if "=" in item)
    return {tok: who for tok, who in pairs if tok}


def caller_principal(authorization: str | None = Header(default=None)) -> str | None:
    """Resolve the caller from its credential. None means anonymous."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    for known, principal in _api_keys().items():
        if hmac.compare_digest(token, known):
            return principal
    return None


@app.post("/chat")
def chat(req: ChatRequest, principal: str | None = Depends(caller_principal)) -> dict:
    # 1. INPUT: block a direct injection in the user prompt, scrub its PII.
    verdict = filter_input(req.prompt)
    if verdict["blocked"]:
        return {"blocked": True, "layer": "input", "reason": verdict["reason"]}

    # 2. CONTAINMENT: break the lethal trifecta. Untrusted content has two
    #    sources, not one: a retrieved document, and (in a public-facing app) the
    #    user, who can type the attacker instruction straight into the prompt. If
    #    either untrusted source is present AND an external tool is requested,
    #    refuse: those must never co-occur with private-data access. This is
    #    architectural, not a classifier. Only an authenticated principal on
    #    the server-side allowlist relaxes the user leg; nothing in the body can.
    retrieved_untrusted = bool(req.retrieved)
    user_untrusted = principal not in TRUSTED_PRINCIPALS
    if (retrieved_untrusted or user_untrusted) and req.allow_external_tool:
        return {"blocked": True, "layer": "containment", "reason": "trifecta_broken"}

    # 3. LLM (stubbed): the scrubbed prompt plus any retrieved document.
    context = verdict["clean_prompt"]
    if req.retrieved:
        context = f"{context}\n[DOC]{req.retrieved}"
    response = stub_llm(context)

    # 4. OUTPUT: hazard check, outbound-URL exfiltration check, and PII redaction
    #    on the response. The exfil check catches the markdown-image data-leak
    #    channel cheaply, but this layer still scores only text: it cannot tell an
    #    instruction came from the untrusted doc, which is why indirect injection
    #    (an instruction, not a URL) still slips through here.
    out = filter_output(response)
    if out["blocked"]:
        return {"blocked": True, "layer": "output", "reason": out["reason"]}
    return {
        "blocked": False,
        "response": out["response"],
        "untrusted_in_context": retrieved_untrusted,
    }
