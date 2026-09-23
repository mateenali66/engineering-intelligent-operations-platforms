# Chapter 16: Securing and Governing AI Systems

Companion code for the layered guardrail proxy and attack harness. The
deterministic pipeline runs headless in CI with no API key and no GPU; Prompt
Guard 2, Llama Guard 4, Presidio's NER, Guardrails AI, NeMo Guardrails, and the
managed cloud guardrails are validation-only and clearly labeled.

## Listing-to-file map

| Listing | File | What it shows |
|---|---|---|
| 16-1 | `guardrails/input_filters.py` (`filter_input`) | the input layer: block a direct injection, scrub PII from the prompt |
| 16-2 | `guardrails/proxy.py` (`chat`) | the layered proxy: input, the lethal-trifecta containment check, the stubbed model, output |
| 16-3 | `tests/test_attacks.py` | the attack harness: direct jailbreak, indirect injection, trifecta exfiltration, benign control, malicious-user trifecta, markdown-image exfiltration, paraphrased-jailbreak bypass |

## Layout

```
guardrails/        detectors, input/output filters, the FastAPI proxy, the pickle-danger demo,
                   and the validation-only labs (lab_promptguard, lab_llamaguard, lab_presidio)
tests/             test_attacks (the 7 attack cases + 4 trust-boundary cases) + test_filters (detector units)
run_smoke.py       headless end-to-end; prints "smoke: ok"
requirements.txt           deterministic CI deps (Python 3.12)
requirements-presidio.txt  optional production PII path
```

## Run

No API key, no GPU. Python 3.12 (so the optional Presidio and modelscan jobs,
which cap below 3.14 / 3.13, can share one interpreter).

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

python run_smoke.py            # prints the 7 attack outcomes, 2 trust cases, the pickle demo, then "smoke: ok"
python -m pytest tests/ -q     # 16 passed
python guardrails/lab_pickle_danger.py   # demonstrates pickle executing code on load
```

The seven attack outcomes the smoke test prints: A direct jailbreak blocked at the
input layer, B indirect injection NOT blocked by output filtering (the injected
text reaches the response, flagged `untrusted_in_context`), C trifecta
exfiltration blocked at the containment layer, D benign request passes, E a
malicious user completing the trifecta with no RAG (blocked at containment once
the user is treated as untrusted, the public-facing default), F the markdown-image
exfiltration channel blocked at the output layer's outbound-URL check, and G a
paraphrased jailbreak that bypasses the input regex (NOT blocked at input). That
pattern is the chapter's thesis: filtering is bypassable (B, G), architectural
containment is the control that holds (C, E), and a cheap deterministic output
check still earns its place (F).

Trust is established on the server, not in the request. The caller sends a bearer
token; the proxy maps it to a principal from the `GUARDRAIL_API_KEYS` server
setting and trusts the user only if that principal is on the server-side
`TRUSTED_PRINCIPALS` allowlist. The test suite proves the boundary: an
authenticated internal service may use a tool (H), a request that carries its own
`trusted_user` flag is rejected with HTTP 422 (I), a forged token is anonymous and
so untrusted (J), and a trusted caller still cannot pair a tool with an untrusted
retrieved document (K). In production, verify an OIDC token or mTLS identity at
the gateway instead of a static key table.

## What CI proves (and what it does not)

The `ch16-guardrails` job runs the deterministic proxy, the attack harness, the
detector units, and the pickle-danger demo for real. The production guardrails
are validation-only: Prompt Guard 2 (gated HF download), Llama Guard 4 (12B,
needs a GPU), Presidio's NER (probabilistic; a separate optional job), Guardrails
AI and NeMo Guardrails (need an LLM or a hub token), and the AWS Bedrock / Azure
managed guardrails (need cloud credentials). They are `py_compile`-checked.
