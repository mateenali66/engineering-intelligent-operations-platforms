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
`trusted_user` defaults to False (public-facing: treat the user as untrusted).
Set it True only for an internal-tool deployment where the caller is authenticated
and the request itself is trusted.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from .input_filters import filter_input
from .output_filters import filter_output

app = FastAPI(title="Guardrail Proxy")


class ChatRequest(BaseModel):
    prompt: str
    retrieved: str = ""           # untrusted retrieved document (RAG context)
    allow_external_tool: bool = False
    trusted_user: bool = False    # False = public-facing: the user is untrusted too


def stub_llm(context: str) -> str:
    """Deterministic stand-in for the LLM, so the pipeline runs with no key."""
    return f"ECHO: {context[:80]}"


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    # 1. INPUT: block a direct injection in the user prompt, scrub its PII.
    verdict = filter_input(req.prompt)
    if verdict["blocked"]:
        return {"blocked": True, "layer": "input", "reason": verdict["reason"]}

    # 2. CONTAINMENT: break the lethal trifecta. Untrusted content has two
    #    sources, not one: a retrieved document, and (in a public-facing app) the
    #    user, who can type the attacker instruction straight into the prompt. If
    #    either untrusted source is present AND an external tool is requested,
    #    refuse: those must never co-occur with private-data access. This is
    #    architectural, not a classifier. trusted_user relaxes the user leg for an
    #    internal-tool deployment where the caller is authenticated and trusted.
    retrieved_untrusted = bool(req.retrieved)
    user_untrusted = not req.trusted_user
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
