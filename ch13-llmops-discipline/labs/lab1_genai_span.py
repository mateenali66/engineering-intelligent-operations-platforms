"""Listing 13-1 (RUNS IN CI): instrument an LLM call with the OpenTelemetry
GenAI semantic conventions, then capture and assert the span offline.

The insight that makes this CI-runnable: you do NOT need a real LLM to emit and
assert GenAI spans. The semantic conventions describe the *shape* of the
telemetry (span name, gen_ai.* attributes), not the model behind it. So we
instrument a STUBBED chat function that returns a canned completion, set the
gen_ai.* attributes the convention asks for, and read the span back through an
InMemorySpanExporter. No API key, no network, no collector.

GenAI semantic conventions (mid-2026, experimental). The current attribute for
the provider is `gen_ai.provider.name`; the older `gen_ai.system` is deprecated.
We set both so the listing reads cleanly against tools that still look for the
legacy name, and we assert on the current one. Span name is, per the spec,
`{gen_ai.operation.name} {gen_ai.request.model}`.

In production you would point the OTLP exporter at a collector or an LLM-native
backend such as Langfuse (see `production_otlp_exporter` below). That export
needs a running endpoint, so CI uses the in-memory exporter instead. The OTLP
wiring is shown but not exercised: it is the production target, validation-only.

Run:
    export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
    python lab1_genai_span.py
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

# GenAI semantic-convention attribute keys. These are string constants in the
# spec; we name them here so the instrumentation below reads against the
# convention rather than against magic strings. (opentelemetry-semantic-
# conventions ships gen_ai constants, but the gen_ai namespace is experimental
# and its Python symbol names churn between releases, so we pin the literals.)
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"   # current (replaces gen_ai.system)
GEN_AI_SYSTEM = "gen_ai.system"                 # deprecated alias, set for compat
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_RESPONSE_ID = "gen_ai.response.id"
GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"


def stub_chat(model: str, prompt: str) -> dict:
    """A stand-in for a real chat completion call.

    Returns the same response shape a provider SDK would (text plus usage), but
    deterministically and with no network. The instrumentation around it is
    identical to what you would write around a live client; only this function
    body changes when you swap in the real model.
    """
    answer = (
        "Restart the checkout deployment: the p95 latency tripled right after "
        "the 14:02 rollout, which matches a bad-config regression."
    )
    return {
        "id": "chatcmpl-stub-0001",
        "model": model,
        "text": answer,
        "finish_reason": "stop",
        # A real SDK reports these; here they are fixed so the listing is
        # deterministic. We never invent a "realistic" token count and pass it
        # off as measured: these are the stub's own declared values.
        "input_tokens": 41,
        "output_tokens": 32,
    }


def traced_chat(tracer: trace.Tracer, model: str, prompt: str) -> dict:
    """Call the (stubbed) model inside a GenAI span and set gen_ai.* attributes.

    The span name follows the convention: "{operation} {model}", e.g.
    "chat anomaly-copilot-v1".
    """
    operation = "chat"
    span_name = f"{operation} {model}"
    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute(GEN_AI_OPERATION_NAME, operation)
        span.set_attribute(GEN_AI_PROVIDER_NAME, "phono.anomaly-copilot")
        span.set_attribute(GEN_AI_SYSTEM, "phono.anomaly-copilot")
        span.set_attribute(GEN_AI_REQUEST_MODEL, model)
        span.set_attribute(GEN_AI_REQUEST_TEMPERATURE, 0.0)
        span.set_attribute(GEN_AI_REQUEST_MAX_TOKENS, 256)

        result = stub_chat(model, prompt)

        span.set_attribute(GEN_AI_RESPONSE_MODEL, result["model"])
        span.set_attribute(GEN_AI_RESPONSE_ID, result["id"])
        span.set_attribute(
            GEN_AI_RESPONSE_FINISH_REASONS, [result["finish_reason"]]
        )
        span.set_attribute(GEN_AI_USAGE_INPUT_TOKENS, result["input_tokens"])
        span.set_attribute(GEN_AI_USAGE_OUTPUT_TOKENS, result["output_tokens"])
        return result


def build_tracer() -> tuple[trace.Tracer, InMemorySpanExporter]:
    """Wire a TracerProvider with an in-memory exporter for offline assertions.

    SimpleSpanProcessor exports synchronously, so by the time the span closes the
    exporter already holds it. That is what makes the assertions below reliable
    in a test without a flush race.
    """
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("ch13.lab1.genai")
    return tracer, exporter


def production_otlp_exporter():  # pragma: no cover - validation-only
    """Production target (NOT run in CI): export GenAI spans over OTLP.

    Point this at an OpenTelemetry Collector or an LLM-native backend such as
    Langfuse. Langfuse exposes an OTLP/HTTP endpoint and reads the same gen_ai.*
    attributes set above, so the trace shows up as an LLM generation with token
    counts and latency. This needs a running endpoint and (for Langfuse Cloud)
    credentials, so CI uses the in-memory exporter instead and only compiles this
    function. Mirrors how Chapter 12's Phoenix path is validation-only.

        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Langfuse OTLP endpoint, e.g. https://cloud.langfuse.com/api/public/otel
        exporter = OTLPSpanExporter(
            endpoint="http://otel-collector:4318/v1/traces",
        )
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(exporter))
        return provider
    """
    raise NotImplementedError(
        "production_otlp_exporter is validation-only: it needs a running OTLP "
        "collector or Langfuse endpoint. CI uses the in-memory exporter."
    )


def run() -> dict:
    """Emit one GenAI span through the stubbed chat and return the captured span.

    Returns a small dict the smoke test asserts against: the span name and its
    gen_ai.* attributes.
    """
    tracer, exporter = build_tracer()
    traced_chat(tracer, model="anomaly-copilot-v1", prompt="checkout p95 tripled")

    spans = exporter.get_finished_spans()
    assert len(spans) == 1, f"expected exactly one span, got {len(spans)}"
    span = spans[0]
    attrs = dict(span.attributes)
    return {"name": span.name, "attributes": attrs}


if __name__ == "__main__":
    captured = run()
    print(f"span name: {captured['name']}")
    print("gen_ai.* attributes captured:")
    for key in sorted(captured["attributes"]):
        if key.startswith("gen_ai."):
            print(f"  {key} = {captured['attributes'][key]}")
