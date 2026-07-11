# Backstage scaffolder skeleton file (templated, not standalone Python).
# The fetch:template step fills in the service name and the OTLP endpoint,
# so the scaffolded service emits telemetry from its first deploy.
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

provider = TracerProvider(
    resource=Resource.create({"service.name": "${{ values.name }}"})
)
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="${{ values.otelEndpoint }}"))
)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("${{ values.name }}")
