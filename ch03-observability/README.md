# Chapter 03: Observability for Intelligent Systems

Code for Chapter 3. Each listing in the printed book maps to a file here. This
chapter builds the book's backbone telemetry stack: an OpenTelemetry Collector
(agent plus gateway) that dual-routes telemetry to real-time backends for humans
and to an S3 lake for ML, plus the feature job that turns the lake into the
table Chapter 6 trains on.

| Listing | File | Description |
|---|---|---|
| 3-1 | `operator/otel-collector-cr.yaml` | OpenTelemetry Operator custom resources: a DaemonSet agent on every node and a gateway Deployment that does the stateful tail sampling, span-metrics derivation, and fan-out |
| 3-2 | `collector-config/otel-collector-config.yaml` | Dual-routing Collector config: OTLP in; batch, resource, and tail_sampling processors; the spanmetrics connector deriving request rate/latency/error metrics from the unsampled span stream; exporters to Prometheus (prometheusremotewrite), Tempo/Jaeger (otlp), Loki (otlphttp to /otlp), and the S3 ML lake (contrib awss3) |
| 3-3 | `feature-job/extract_features.py` | Feature-extraction job: read flattened parquet from S3, window and mean-aggregate per (service, window), report per-column coverage, emit the feature table. The literal handoff artifact to Chapter 6 |
| 3-4 | `log-features/drain_templates.py` | Drain-based log-template extraction: raw log lines to template ids to a per-window count vector |
| helper | `feature-job/flatten_otlp.py` | Reads the awss3 OTLP-protobuf objects and flattens them to one parquet row per metric data point (timestamp, service_name, metric_name, value). Gauges and sums flatten directly; histograms (how latency arrives) become derived `.count`/`.sum`/`.error_count`/`.avg` records. Run before `extract_features.py` |
| smoke | `feature-job/run_smoke.py` | Cluster-free smoke test: a synthetic OTLP fixture (`feature-job/fixtures/otlp_metrics_sample.json`) flows through the flattener and the feature job, and every expected feature column must come out populated. CI runs this |

## Pinned versions

| Component | Version | Why pinned |
|---|---|---|
| otel/opentelemetry-collector-contrib | 0.135.0 | `awss3`, `tail_sampling`, and the `spanmetrics` connector ship only in contrib |
| opentelemetry-operator | 0.135.0 | `OpenTelemetryCollector` CR, apiVersion `opentelemetry.io/v1beta1` |
| Prometheus | 3.5.0 | remote-write receiver target |
| Grafana Tempo | 2.8.2 | OTLP trace ingest |
| Grafana Loki | 3.5.5 | native OTLP endpoint at `/otlp`; needs `allow_structured_metadata: true` |
| Grafana | 11.6.0 | dashboards over Prometheus/Tempo/Loki |
| OpenTelemetry Demo (Astronomy Shop) | 2.0.x | the instrumented sample app |
| Python | 3.12 | feature job and Drain snippet |
| pandas | 2.2.3 | windowing and aggregation |
| pyarrow | 17.0.0 | parquet read/write |
| s3fs | 2024.10.0 | read/write parquet on S3 |
| drain3 | 0.9.11 | log-template extraction |
| opentelemetry-proto | 1.27.0 | OTLP protobuf bindings for the flattener |

`requirements.txt` in this directory pins the Python dependencies.

## Notes

- The `loki` standalone exporter has been removed from contrib. Listing 3-2 uses
  `otlphttp` against Loki's native OTLP endpoint (`/otlp`). Do not reintroduce
  the old exporter.
- `prometheusremotewrite` needs Prometheus started with
  `--web.enable-remote-write-receiver`; that endpoint is off by default.
- `awss3` is the real contrib exporter with its `s3uploader` block. Verify it in
  the contrib distribution for the version you pin before deploying.
- `tail_sampling` is stateful: it must see every span of a trace, so it lives on
  the gateway tier (Listing 3-1), never on the per-node agents. The gateway runs
  two replicas, so the agents send traces through the `loadbalancing` exporter,
  which hashes the trace ID to pick a replica. Its `k8s` resolver watches the
  gateway's headless Service, which needs the Role at the end of the CR file.
  Metrics and logs go through the ordinary `gateway-collector` Service.
- The `spanmetrics` connector hangs off the UNSAMPLED `traces/lake` pipeline, so
  its rates are true rates, and it emits `traces.span.metrics.calls` and the
  `traces.span.metrics.duration` histogram (dimensions include `status.code`,
  where `STATUS_CODE_ERROR` marks errored series). It runs with delta
  temporality for the lake; do not route that delta stream to
  `prometheusremotewrite`, which expects cumulative metrics.
- Metric names in `extract_features.py`'s `METRIC_COLUMNS` were verified
  against OpenTelemetry Demo 2.0 on collector-contrib 0.135.0. The Demo's
  per-language SDK metric coverage is uneven, which is why the feature job
  reads span-derived metrics instead of SDK HTTP metrics.

## Run the lab

Deploy the OpenTelemetry Demo to a Kubernetes cluster, install the OpenTelemetry
Operator, apply `operator/otel-collector-cr.yaml`, and point the demo's OTLP
exporter (`OTEL_EXPORTER_OTLP_ENDPOINT`) at the agent service. Within a minute
or two Grafana's Explore view should show demo metrics in Prometheus, traces in
Tempo, and logs in Loki, and the S3 bucket should start gaining hourly
partitions under `otel/YYYY/MM/DD/HH/`. Then run `feature-job/flatten_otlp.py`
to turn the awss3 OTLP-protobuf objects into flat parquet, run
`feature-job/extract_features.py` against that flattened prefix, check the
per-column coverage lines it prints, and inspect the resulting feature table.
Chapter 6 picks up exactly that table.

## Test trace affinity

`operator/trace-affinity-test/run.sh` checks that every span of a trace reaches
the same gateway replica. It creates a three-node kind cluster, installs
cert-manager v1.21.2 and Operator v0.135.0, applies the agent resource and its
Role from this directory unchanged, and deploys a two-replica gateway test
double that logs what it receives. It sends 40 traces whose spans are split
across the two agents and fails if any trace reaches more than one replica. It
then scales the gateway to three replicas and repeats the check as soon as the
new pod is Ready. Needs docker, kind, kubectl, and python3 with PyYAML, takes
about five minutes, and deletes the cluster on exit.

If nothing appears:

1. Check the agent pods' logs for export errors (`kubectl logs -n observability
   ds/agent-collector`). "connection refused" to `gateway-collector:4317` means
   the gateway Service is missing or misnamed; the operator names each
   Collector's Service `<name>-collector`. A `forbidden` error on `endpoints`
   means the agent's Role at the end of the CR file was not applied.
2. Confirm the demo's `OTEL_EXPORTER_OTLP_ENDPOINT` points at the agent
   service (gRPC 4317 or HTTP 4318), not at the demo's own bundled collector.
3. Confirm the pods run the CONTRIB image at the pinned version. The core image
   refuses to start with `awss3`, `tail_sampling`, or `spanmetrics` in the
   config, and the pod goes CrashLoopBackOff with an "unknown type" error.

No cluster handy? `python feature-job/run_smoke.py` exercises the flattener and
the feature job against the synthetic OTLP fixture and asserts every feature
column is populated, which is exactly what CI gates on.
