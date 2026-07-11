"""Tests for the convergence check: the substrates are shared, the workloads are
DISCOVERED rather than enumerated, and the check actually FAILS when a substrate
diverges or a de-converged workload is added (so it is a real assertion, not a
rubber stamp)."""

from __future__ import annotations

import copy
import shutil

import pytest

from aiosp import convergence
from aiosp.convergence import (
    OTLP_ENV,
    check,
    collector_endpoint,
    discover_workloads,
)


def test_discovers_the_three_workloads():
    # Discovered from platform/inference/, not read off a hand-kept list.
    assert set(discover_workloads()) == {
        "anomaly-detector",
        "churn-model",
        "incident-copilot",
    }


def test_all_three_disciplines_present():
    report = check()
    assert {d for _, d, _ in report["rows"]} == {"AIOps", "MLOps", "LLMOps"}


def test_convergence_passes_on_the_real_manifests():
    report = check()
    assert report["serving"] == (
        "serving.kserve.io/v1beta1",
        "InferenceService",
    )
    formats = {fmt for _, _, fmt in report["rows"]}
    # Predictive AND generative on the same kind: the unification claim.
    assert "sklearn" in formats
    assert "huggingface" in formats
    assert report["observability"] == collector_endpoint()


def test_collector_endpoint_is_derived_from_the_service():
    # Not hard-coded: it is built from the Service name/namespace/port, and the
    # Service selector is asserted to match the running Collector Deployment.
    assert collector_endpoint() == "http://otel-collector.observability:4318"


def test_divergent_observability_endpoint_fails(monkeypatch):
    # If one workload's model server exported to a different Collector, the
    # platform would not be converged. Simulate it by loading that one manifest
    # with a changed OTLP env value and confirm the check raises.
    real_load = convergence._load

    def fake_load(path):
        doc = copy.deepcopy(real_load(path))
        if path.name == "incident-copilot.yaml" and doc.get("kind") == "InferenceService":
            for var in doc["spec"]["predictor"]["model"]["env"]:
                if var["name"] == OTLP_ENV:
                    var["value"] = "http://rogue-collector.other:4318"
        return doc

    monkeypatch.setattr(convergence, "_load", fake_load)
    with pytest.raises(AssertionError):
        check()


def test_divergent_serving_api_fails(monkeypatch):
    # If one workload were served on a different API/kind, the serving substrate
    # would not be shared. Change one InferenceService's apiVersion and confirm
    # the serving assertion (not just observability) fails.
    real_load = convergence._load

    def fake_load(path):
        doc = copy.deepcopy(real_load(path))
        if path.name == "anomaly-detector.yaml" and doc.get("kind") == "InferenceService":
            doc["apiVersion"] = "serving.kserve.io/v1alpha1"
        return doc

    monkeypatch.setattr(convergence, "_load", fake_load)
    with pytest.raises(AssertionError):
        check()


def test_divergent_delivery_repo_fails(monkeypatch):
    # If one workload were delivered from a different repo, the delivery substrate
    # would not be shared. Change one Argo CD Application's repoURL and confirm the
    # delivery assertion fails.
    real_load = convergence._load

    def fake_load(path):
        doc = copy.deepcopy(real_load(path))
        if path.name == "churn-model.yaml" and doc.get("kind") == "Application":
            doc["spec"]["source"]["repoURL"] = "https://github.com/rogue/other.git"
        return doc

    monkeypatch.setattr(convergence, "_load", fake_load)
    with pytest.raises(AssertionError):
        check()


def test_deconverged_extra_workload_is_discovered_and_fails(tmp_path, monkeypatch):
    # De-convergence arrives as the workload nobody added to a list. Copy the real
    # platform tree, add a FOURTH InferenceService on a divergent serving API (plus
    # a matching Application), and confirm the DISCOVERING check catches it even
    # though no hand-kept list names it. A check that enumerated names would miss it.
    dst = tmp_path / "platform"
    shutil.copytree(convergence.PLATFORM, dst)
    (dst / "inference" / "rogue-detector.yaml").write_text(
        "apiVersion: serving.kserve.io/v1alpha1\n"  # divergent serving API
        "kind: InferenceService\n"
        "metadata:\n"
        "  name: rogue-detector\n"
        "  namespace: aiops\n"
        "spec:\n"
        "  predictor:\n"
        "    model:\n"
        "      modelFormat:\n"
        "        name: sklearn\n"
        "      env:\n"
        "        - name: OTEL_EXPORTER_OTLP_ENDPOINT\n"
        "          value: http://otel-collector.observability:4318\n"
        "      storageUri: gs://kfserving-examples/models/sklearn/1.0/model\n"
    )
    (dst / "apps" / "rogue-detector.yaml").write_text(
        "apiVersion: argoproj.io/v1alpha1\n"
        "kind: Application\n"
        "metadata:\n"
        "  name: rogue-detector\n"
        "  namespace: argocd\n"
        "spec:\n"
        "  project: aiosp\n"
        "  source:\n"
        "    repoURL: https://github.com/YOUR-USERNAME/aiosp-platform.git\n"
        "    targetRevision: main\n"
        "    path: platform/inference\n"
        "  destination:\n"
        "    server: https://kubernetes.default.svc\n"
        "    namespace: aiops\n"
    )
    monkeypatch.setattr(convergence, "PLATFORM", dst)
    assert set(discover_workloads()) == {
        "anomaly-detector",
        "churn-model",
        "incident-copilot",
        "rogue-detector",
    }
    with pytest.raises(AssertionError):
        check()


def test_workload_without_a_matching_application_fails(tmp_path, monkeypatch):
    # An InferenceService delivered outside the checked GitOps tree (no Argo CD
    # Application) breaks the one-to-one correspondence and fails the check.
    dst = tmp_path / "platform"
    shutil.copytree(convergence.PLATFORM, dst)
    (dst / "apps" / "churn-model.yaml").unlink()
    monkeypatch.setattr(convergence, "PLATFORM", dst)
    with pytest.raises(AssertionError):
        check()
