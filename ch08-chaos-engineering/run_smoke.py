"""End-to-end chaos flywheel on synthetic telemetry (CI entry point).

Inject a known fault, confirm the Chapter 6 detector lights up during it, run an
LLM-drafted experiment through the review gate, export labeled windows, and prove
the labels round-trip into the actual Chapter 6 loader. Asserts the flywheel: a
chaos experiment manufactures labeled training data the Chapter 6 detector can
consume unchanged.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import yaml

from pipeline.correlate import check_hypothesis, fault_response
from pipeline.export_labels import export_training_data
from pipeline.make_telemetry import make_telemetry
from pipeline.review_gate import review_experiment

CH06 = os.path.join(os.path.dirname(__file__), "..", "ch06-anomaly-detection")


def main():
    # Validate the Chaos Mesh manifests parse and target chaos-mesh.org/v1alpha1.
    for name in ("pod-kill", "network-delay"):
        with open(f"experiments/{name}.yaml") as fh:
            manifest = yaml.safe_load(fh)
        assert manifest["apiVersion"] == "chaos-mesh.org/v1alpha1"
        print(f"manifest {name}: {manifest['kind']} ok")

    # Inject a fault and analyze the response. The analysis has two halves.
    df, fault = make_telemetry()

    # Half 1, the steady-state hypothesis: p99 latency < 500 ms, errors < 1 %.
    # The synthetic capture above is standardized for the detector, so the
    # hypothesis runs on a small fixture of real-scale measurements (real
    # milliseconds and error fractions), exactly as it would on a live cluster
    # over the Chapter 3 feature table for the experiment window. A "held" pod
    # kill stays inside the SLO; a "breached" one exceeds it.
    held = pd.DataFrame({"request_latency_ms": np.linspace(120, 470, 100),
                         "error_rate": np.full(100, 0.006)})
    breached = pd.DataFrame({"request_latency_ms": np.linspace(300, 900, 100),
                             "error_rate": np.full(100, 0.025)})
    hypothesis = check_hypothesis(held)
    print("hypothesis:", hypothesis)
    assert hypothesis["verdict"] == "PASS", "the pod kill should hold the SLO"
    assert check_hypothesis(breached)["verdict"] == "FAIL", "a breach must FAIL"

    # Half 2, the detector: did the Chapter 6 detector light up in the window?
    resp = fault_response(df, fault)
    print("fault response:", resp)
    assert resp["detector_lit_up"], "the detector should light up in the fault window"

    # The review gate blocks an over-broad LLM-drafted experiment.
    risky = {"spec": {"mode": "all", "duration": "10m",
                      "selector": {"namespaces": ["kube-system"]}}}
    gate = review_experiment(risky)
    print("review gate (risky):", gate)
    assert gate["auto_blocked"], "the gate should block the over-broad experiment"

    # The gate also closes the two silent holes: a missing duration and a wide
    # fixed-count mode both raise findings instead of passing clean.
    no_duration = {"spec": {"mode": "one",
                            "selector": {"namespaces": ["default"]}}}
    wide_fixed = {"spec": {"mode": "fixed", "value": "500", "duration": "30s",
                           "selector": {"namespaces": ["default"]}}}
    assert review_experiment(no_duration)["auto_blocked"], "missing duration must block"
    assert review_experiment(wide_fixed)["auto_blocked"], "wide fixed mode must block"

    # Export labeled windows and round-trip them through the Chapter 6 loader.
    labeled = export_training_data(df, fault, "data/fault_labeled.parquet")
    print(f"exported {int(labeled['label'].sum())} fault-labeled windows")

    sys.path.insert(0, CH06)
    from pipeline.data import load_feature_table  # Chapter 6's own loader

    X, y, names = load_feature_table("data/fault_labeled.parquet")
    print(f"Chapter 6 loaded it: {X.shape[0]} rows, {len(names)} features, "
          f"{int(y.sum())} labeled faults")
    assert y.sum() > 0 and X.shape[0] == len(df), "labels must round-trip into Ch6"
    print("smoke: ok")


if __name__ == "__main__":
    main()
