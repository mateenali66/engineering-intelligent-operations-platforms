"""Listing 17-1 (RUNS IN CI): one trace that carries infra and gen_ai telemetry
together, so token and cost appear beside Kubernetes and HTTP spans in one view.

The unified platform's payoff for observability is that the LLM is not a separate
monitoring island. An incident investigation starts as an ordinary infra span
(an HTTP handler in a namespace on a node) and, when it calls the Incident
Copilot, that call is a CHILD span in the SAME trace, tagged with the
OpenTelemetry GenAI semantic conventions plus a computed cost. Open the trace in
Grafana and you see the infra work and the model work, with tokens and dollars,
on one timeline.

This is CI-runnable for the Chapter 13 reason: the GenAI conventions describe the
SHAPE of the telemetry, not the model. We stub the model, set the gen_ai.*
attributes a real client would, and read the spans back through an in-memory
exporter. No LLM, no key, no collector, no GPU.

Run:
    export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
    python -m aiosp.tracing
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from aiosp.cost import APP_GENAI_COST_USD, compute_cost

# GenAI semantic-convention keys (mid-2026, Development status). Current names:
# gen_ai.provider.name replaces the deprecated gen_ai.system; token usage is
# input_tokens/output_tokens, not the older prompt_tokens/completion_tokens.
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"


def build_tracer() -> tuple[trace.Tracer, InMemorySpanExporter]:
    """A TracerProvider with infra resource attributes and an in-memory exporter.

    The Resource carries the same identity an OpenTelemetry agent would attach in
    the cluster (service name, Kubernetes namespace and pod), so the parent span
    looks like real infra telemetry. SimpleSpanProcessor exports synchronously,
    so the exporter holds every span the moment it closes.
    """
    resource = Resource.create(
        {
            "service.name": "incident-api",
            "k8s.namespace.name": "aiops",
            "k8s.pod.name": "incident-api-7c9f-2xk",
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("aiosp.tracing")
    return tracer, exporter


def stub_copilot(model: str, prompt: str) -> dict:
    """Stand-in for the Incident Copilot's generative call (Chapter 15).

    Returns the response shape a real client would, with declared token counts.
    These are the stub's own values, never passed off as a measured generation.
    """
    return {
        "model": model,
        "text": "Roll back the 14:02 checkout deploy; p95 tripled right after it.",
        "input_tokens": 220,
        "output_tokens": 38,
    }


def investigate(tracer: trace.Tracer, alert: str) -> dict:
    """An infra span that calls the Copilot inside a child gen_ai span.

    The parent is ordinary infra work (handling an alert). The child is the model
    call, carrying the gen_ai.* attributes and the computed cost. Both belong to
    one trace, which is the point: no separate LLM telemetry pipeline.
    """
    with tracer.start_as_current_span("POST /incidents/investigate") as parent:
        parent.set_attribute("http.request.method", "POST")
        parent.set_attribute("http.route", "/incidents/investigate")

        model = "incident-copilot"
        operation = "chat"
        with tracer.start_as_current_span(f"{operation} {model}") as gen:
            gen.set_attribute(GEN_AI_OPERATION_NAME, operation)
            gen.set_attribute(GEN_AI_PROVIDER_NAME, "aiosp.kserve")
            gen.set_attribute(GEN_AI_REQUEST_MODEL, model)
            result = stub_copilot(model, alert)
            gen.set_attribute(GEN_AI_RESPONSE_MODEL, result["model"])
            gen.set_attribute(GEN_AI_USAGE_INPUT_TOKENS, result["input_tokens"])
            gen.set_attribute(GEN_AI_USAGE_OUTPUT_TOKENS, result["output_tokens"])
            cost = compute_cost(
                model, result["input_tokens"], result["output_tokens"]
            )
            # Custom attribute: cost is not part of the GenAI convention.
            gen.set_attribute(APP_GENAI_COST_USD, cost)
        return result


def capture(alert: str = "checkout p95 tripled") -> list:
    """Run one investigation and return the finished spans, parent first."""
    tracer, exporter = build_tracer()
    investigate(tracer, alert)
    spans = exporter.get_finished_spans()
    # Child closes before parent, so the exporter holds it first; order by start.
    return sorted(spans, key=lambda s: s.start_time)


if __name__ == "__main__":
    spans = capture()
    trace_ids = {s.context.trace_id for s in spans}
    print(f"spans in trace: {len(spans)}; distinct trace_ids: {len(trace_ids)}")
    for s in spans:
        attrs = dict(s.attributes or {})
        gen = {k: v for k, v in attrs.items() if k.startswith("gen_ai.")}
        kind = "gen_ai" if gen else "infra"
        line = f"  [{kind}] {s.name}"
        if kind == "gen_ai":
            tokens = (
                attrs[GEN_AI_USAGE_INPUT_TOKENS],
                attrs[GEN_AI_USAGE_OUTPUT_TOKENS],
            )
            line += (
                f"  tokens(in/out)={tokens[0]}/{tokens[1]}"
                f"  cost=${attrs[APP_GENAI_COST_USD]}"
            )
        print(line)
