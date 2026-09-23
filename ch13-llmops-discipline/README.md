# Chapter 13: LLMOps - A New Operational Discipline

Code listings for Chapter 13. The running example is a small RAG anomaly-copilot
instrumented end to end: OpenTelemetry GenAI spans, a CI eval gate, and Promptfoo
jailbreak probes.

| Listing | File | Description | CI |
|---|---|---|---|
| 13-1 | `labs/lab1_genai_span.py` | Instrument a (stubbed) LLM call with the OpenTelemetry GenAI semantic conventions; capture and assert the span with an in-memory exporter | RUNS |
| 13-2 | `labs/lab2_eval_gate.py` | A Pytest eval gate (DeepEval `ExactMatchMetric`) that passes the good release and fails on a regression | RUNS |
| 13-2b | `labs/lab2_ragas_online.py` | The Ragas RAG-metric (faithfulness) equivalent of the gate | validation-only |
| 13-3 | `redteam/promptfooconfig.yaml` | Promptfoo jailbreak / prompt-injection red-team probe set | YAML lint only |
| 13-4 | `labs/lab3_cost_meter.py` | A token cost meter: span token counts -> dollars via a price table, per-route spend, a soft line that downshifts to the cheap route, and a hard daily cap enforced by reserving each call's worst-case cost | RUNS |
| - | `labs/run_smoke.py` | Headless smoke test for labs 1-3; prints `smoke: ok` | RUNS |

## What runs in CI vs what is validation-only

Honest split, the same one Chapter 11 (vLLM/GPU) and Chapter 12 (Phoenix) use.
CI has **no LLM API key and no network egress**.

**Runs in CI (no key, no network, no GPU, no collector):**
- Lab 1 emits one GenAI span from a stubbed chat function and asserts the span
  name `chat anomaly-copilot-v1` and the `gen_ai.*` attributes
  (`gen_ai.operation.name`, `gen_ai.provider.name`, request/response model,
  `gen_ai.usage.input_tokens`/`output_tokens`) via an `InMemorySpanExporter`.
- Lab 2 runs the DeepEval `ExactMatchMetric` gate (deterministic, non-LLM): the
  good release scores 1.0 and passes; the regressed release scores 0.0 and a
  real gate fails the build. `pytest` runs both the passing case and the
  asserted-failure case.
- Lab 3 runs the cost meter over the same stubbed token counts: it converts
  tokens to dollars through an explicit price table, accumulates spend per route,
  downshifts to the cheap route past a soft line, and enforces a hard daily cap
  by reserving each call's worst-case cost (real input plus the max_tokens cap)
  before it runs. Deterministic, no key. `run_smoke.py` asserts spend never
  exceeds the cap, a downshift happened, and repeated over-cap requests on either
  route are refused and add no spend. It is an in-process meter; a multi-instance
  deployment keeps reservations in a shared store keyed by date.
- The Promptfoo config is YAML-linted.

**Validation-only (needs an LLM key / a running service; CI compiles but does
not execute):**
- The Langfuse OTLP export in Lab 1 (`production_otlp_exporter`): needs a
  collector or a Langfuse endpoint.
- The LLM-as-judge metric in Lab 2 (`production_llm_judge_metric`, G-Eval) and
  the Ragas online metric (`lab2_ragas_online.py`): need an LLM judge. Note
  `ragas==0.4.3` cannot even be imported offline in the verified mid-2026
  environment (it pulls a removed `langchain_community` module), so the offline
  gate ships on DeepEval and Ragas is the production/online path.
- A live `promptfoo eval` / `promptfoo redteam run`: sends each probe to an LLM
  provider.

## Run

Verified Python 3.14. Both `opentelemetry==1.42.1` and `deepeval==4.0.6` install
cleanly on 3.14; this chapter does not need the 3.12 pin Ch11/Ch12 required.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r labs/requirements.txt

export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
python labs/run_smoke.py            # -> smoke: ok
python -m pytest labs/lab2_eval_gate.py -q

# Promptfoo is a Node/npm tool; live red-team run is local-only (needs a key):
npm install -g promptfoo
export OPENAI_API_KEY=...
promptfoo eval -c redteam/promptfooconfig.yaml
```

Every listing here is version-pinned and CI-tested (job `ch13-llmops`).
