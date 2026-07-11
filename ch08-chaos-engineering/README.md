# Chapter 8: AI-Driven Chaos Engineering

The resilience flywheel: inject a known fault, test the steady-state hypothesis,
confirm the Chapter 6 detector responds, gate an LLM-drafted experiment, and
export fault-labeled windows that load straight back into the Chapter 6 detector
as training data.

| Listing | File | What it is |
|---|---|---|
| Listing 8-1 | `experiments/pod-kill.yaml` | A Chaos Mesh pod-kill experiment with a steady-state hypothesis |
| Listing 8-2 | `pipeline/correlate.py` | The analysis step: check the steady-state hypothesis, and correlate the injected fault with the Chapter 6 detector response |
| Listing 8-3 | `pipeline/review_gate.py` | A human-review gate for an LLM-drafted experiment (blast radius, namespace, duration) |
| Listing 8-4 | `pipeline/export_labels.py` | Export fault-labeled windows in the exact Chapter 6 feature-table schema |

`experiments/network-delay.yaml` is the second fault type. `pipeline/make_telemetry.py`
generates synthetic telemetry with a known injected-fault window, matching the
Chapter 6 schema, so everything runs without a live cluster.

## Run it

```bash
pip install -r requirements.txt          # pinned, CI-tested versions
python run_smoke.py                       # inject -> check -> detect -> gate -> export -> round-trip
# -> manifest pod-kill: PodChaos ok
#    hypothesis: {... 'verdict': 'PASS'}
#    fault response: {... 'detector_lit_up': True}
#    review gate (risky): {'auto_blocked': True, ...}
#    Chapter 6 loaded it: 360 rows, 11 features, 8 labeled faults
#    smoke: ok
```

The hypothesis check (`check_hypothesis`) evaluates the steady-state SLO (p99
latency < 500 ms, error rate < 1 %) in real units. The synthetic capture is
standardized for the detector, so the smoke test exercises `check_hypothesis` on
a small fixture of real-scale measurements (both a held and a breached case); on
a live cluster you feed it the Chapter 3 feature table for the experiment window.

Run commands from this directory (`ch08-chaos-engineering/`). `run_smoke.py`
imports Chapter 6's own `load_feature_table` from the sibling
`ch06-anomaly-detection/` directory to prove the exported labels round-trip into
the detector unchanged, so both chapter directories must be present (they are in
this repo). The Chaos Mesh manifests target `chaos-mesh.org/v1alpha1` and apply on
a cluster with Chaos Mesh 2.8.x installed.

## Create the namespace before applying

The experiment objects set `metadata.namespace: chaos-testing`, so that namespace
must exist or `kubectl apply` is rejected. No other step creates it:

```bash
kubectl create namespace chaos-testing
# namespace/chaos-testing created
```

## Validate the selector before applying

Both manifests select the OpenTelemetry Demo payment service by
`app.kubernetes.io/component: payment` (the demo helm chart labels pods by
component; it sets no plain `app` label). Prove the selector matches before
`kubectl apply`, because an experiment that selects zero pods applies cleanly
and looks exactly like a resilient system:

```bash
kubectl get pods -n default -l app.kubernetes.io/component=payment
# NAME                       READY   STATUS    RESTARTS   AGE
# payment-7d8f9c6b5d-qx4tk   1/1     Running   0          2d1h
```

`No resources found` means the selector matches nothing; fix it before going
further.

## Pinned versions

See `requirements.txt`. Tested against scikit-learn 1.9.0, pandas 2.3.3,
numpy 2.4.6, pyarrow 24.0.0, PyYAML 6.0.2. Chaos Mesh (2.8.x) and LitmusChaos
(3.x) are cluster tools, not pip packages.

## The flywheel

The point of this chapter's code is that a chaos experiment knows the ground truth
(it injected the fault), so it manufactures the labels the unsupervised Chapter 6
detector never had. `export_labels.py` emits the exact Chapter 6 feature table:
14 columns total, which Chapter 6's `load_feature_table` reads as 11 numeric
features plus the three metadata columns `service_name`, `window_start`, and
`label`. The smoke test loads the export back through that loader (reporting "11
features") to prove the two chapters interoperate.
