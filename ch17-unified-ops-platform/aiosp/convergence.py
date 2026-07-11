"""Listing 17-4 (RUNS IN CI): the convergence thesis as an executable test.

The chapter claims AIOps, MLOps, and LLMOps are three workloads on ONE platform:
one serving API, one delivery loop, one observability backend. This module proves
it by DISCOVERING whatever is on the platform (every InferenceService under
platform/inference/) and asserting the shared substrates, rather than trusting a
hand-kept list. De-convergence arrives as the workload nobody added to the list,
so the check must find workloads, not enumerate them.

For each discovered workload it asserts:

  serving       every workload is the SAME kind on the SAME KServe API
                (serving.kserve.io/v1beta1, InferenceService), with predictive
                AND generative model formats sharing that one kind.
  delivery      every workload has a matching Argo CD Application (one per
                InferenceService, none orphaned) that pulls from the SAME repo
                onto the SAME cluster: one reconciliation loop.
  observability every workload's model server sets OTEL_EXPORTER_OTLP_ENDPOINT to
                the SAME Collector Service, and that Service selects the running
                Collector Deployment: the export is wired, not just declared.

If any substrate is not shared, or a workload has no Application (or an Application
has no workload), the check fails. That is the difference between a converged
platform and three parallel stacks wearing one diagram.

Run:
    python -m aiosp.convergence
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

PLATFORM = Path(__file__).resolve().parent.parent / "platform"
OTLP_ENV = "OTEL_EXPORTER_OTLP_ENDPOINT"
ROOT_APP = "aiosp-root"

# Discipline label per namespace, for the human-readable report only. A namespace
# outside this map is reported by its own (upper-cased) name, so a new tenant is
# never silently dropped from the report.
DISCIPLINE = {"aiops": "AIOps", "mlops": "MLOps", "llmops": "LLMOps"}


def _load(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)


def _load_all(path: Path) -> list:
    with path.open() as fh:
        return [d for d in yaml.safe_load_all(fh) if d]


def collector_endpoint() -> str:
    """Derive the canonical OTLP endpoint from the Collector manifest.

    Returns http://{service}.{namespace}:{otlp-http-port}, the address every
    workload must export to. Also asserts the Service selector matches the
    Collector Deployment's pod labels, so the endpoint resolves to a Collector
    that actually runs rather than a Service selecting nothing.
    """
    docs = _load_all(PLATFORM / "observability" / "otel-collector.yaml")
    svc = next(d for d in docs if d["kind"] == "Service")
    dep = next(d for d in docs if d["kind"] == "Deployment")
    selector = svc["spec"]["selector"]
    pod_labels = dep["spec"]["template"]["metadata"]["labels"]
    assert selector.items() <= pod_labels.items(), (
        f"Collector Service selector {selector} matches no Deployment pod "
        f"labels {pod_labels}: the endpoint would resolve to zero backends"
    )
    name = svc["metadata"]["name"]
    namespace = svc["metadata"]["namespace"]
    http_port = next(
        p["port"] for p in svc["spec"]["ports"] if p["name"] == "otlp-http"
    )
    return f"http://{name}.{namespace}:{http_port}"


def discover_workloads() -> list[str]:
    """Discover workload names by globbing the InferenceService manifests.

    The list is not hand-kept: a fourth workload dropped into platform/inference/
    is found here, so it cannot escape the substrate assertions below.
    """
    names = []
    for path in sorted((PLATFORM / "inference").glob("*.yaml")):
        doc = _load(path)
        if doc.get("kind") == "InferenceService":
            names.append(doc["metadata"]["name"])
    return names


def discover_applications() -> dict:
    """Discover the workload Argo CD Applications, keyed by name (root excluded)."""
    apps = {}
    for path in sorted((PLATFORM / "apps").glob("*.yaml")):
        doc = _load(path)
        if doc.get("kind") != "Application":
            continue
        if doc["metadata"]["name"] == ROOT_APP:
            continue
        apps[doc["metadata"]["name"]] = doc
    return apps


def _otlp_endpoint(isvc: dict) -> str:
    """The OTLP endpoint the model server actually exports to (an env var, not a
    label): read it from spec.predictor.model.env so the assertion checks behavior."""
    env = isvc["spec"]["predictor"]["model"].get("env", [])
    for var in env:
        if var["name"] == OTLP_ENV:
            return var["value"]
    raise AssertionError(
        f"{isvc['metadata']['name']}: model server sets no {OTLP_ENV}"
    )


def check() -> dict:
    """Assert the three shared substrates and return a per-workload report.

    Raises AssertionError on the first substrate that is not shared, or if the
    discovered workloads and Applications do not correspond one to one.
    """
    services = {}
    deliveries = {}
    observed = {}
    rows = []

    endpoint = collector_endpoint()
    names = discover_workloads()
    apps = discover_applications()

    # Every InferenceService has an Application, and no Application is orphaned.
    assert set(names) == set(apps), (
        f"workloads and Applications diverge: "
        f"services={sorted(names)} apps={sorted(apps)}"
    )

    for name in names:
        isvc = _load(PLATFORM / "inference" / f"{name}.yaml")
        app = apps[name]
        namespace = isvc["metadata"]["namespace"]
        discipline = DISCIPLINE.get(namespace, namespace.upper())

        services[name] = (isvc["apiVersion"], isvc["kind"])
        fmt = isvc["spec"]["predictor"]["model"]["modelFormat"]["name"]

        repo = app["spec"]["source"]["repoURL"]
        cluster = app["spec"]["destination"]["server"]
        deliveries[name] = (app["apiVersion"], app["kind"], repo, cluster)

        otlp = _otlp_endpoint(isvc)
        observed[name] = otlp
        assert otlp == endpoint, (
            f"{name}: OTLP endpoint {otlp} != Collector {endpoint}"
        )

        rows.append((name, discipline, fmt))

    # serving: one API + kind across all workloads, predictive and generative.
    serving_apis = set(services.values())
    assert serving_apis == {("serving.kserve.io/v1beta1", "InferenceService")}, (
        f"serving substrate not shared: {serving_apis}"
    )
    formats = {fmt for _, _, fmt in rows}
    assert "sklearn" in formats and "huggingface" in formats, (
        f"expected predictive AND generative formats, got {formats}"
    )

    # delivery: one Argo API + kind + repo + cluster across all workloads.
    delivery_set = {(api, kind, repo, cl) for api, kind, repo, cl in deliveries.values()}
    assert len(delivery_set) == 1, f"delivery substrate not shared: {delivery_set}"

    # observability: one endpoint, wired into every model server's OTLP exporter.
    assert len(set(observed.values())) == 1, "observability substrate not shared"

    return {
        "serving": serving_apis.pop(),
        "delivery": delivery_set.pop(),
        "observability": endpoint,
        "rows": rows,
    }


def main() -> int:
    report = check()
    api, kind = report["serving"]
    print("AIOSP convergence check")
    print(f"  serving:       {kind} on {api}  (one API for all workloads)")
    _, _, repo, cluster = report["delivery"]
    print(f"  delivery:      Argo CD Application from {repo}")
    print(f"                 onto {cluster}  (one reconciliation loop)")
    print(f"  observability: OTLP to {report['observability']}  (one backend)")
    print("  workloads:")
    for name, discipline, fmt in report["rows"]:
        served = "generative" if fmt == "huggingface" else "predictive"
        print(f"    {discipline:<7} {name:<18} {served:<11} (modelFormat={fmt})")
    print("  PASS: three disciplines, one substrate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
