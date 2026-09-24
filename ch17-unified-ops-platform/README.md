# Chapter 17: The Unified Ops Platform

The capstone. AIOSP, the AI Operations Substrate Platform, an intelligent
operations platform that runs the AIOps anomaly detector, the LLMOps Incident
Copilot, and a churn model (a second predictive workload) on ONE substrate:
Kubernetes for compute, OpenTelemetry for observability, Argo CD (GitOps) for
delivery, and parallel registries for the artifacts.

The chapter's claim is that these three disciplines are three workloads on one
platform, not three products. This directory proves it two ways that run with no
cluster, no LLM key, and no GPU: a convergence check that reads the real GitOps
manifests and asserts the shared substrates, and a unified trace that puts the
model's tokens and cost on the same trace as the infra work.

## Listing-to-file map

| Listing | File | Description |
|---|---|---|
| 17-1 | `aiosp/tracing.py` (`investigate`) | One trace carrying an infra parent span and a gen_ai child span, with token usage and a computed cost |
| 17-2 | `platform/apps/root.yaml` | The app-of-apps root Argo CD Application that delivers all three workloads |
| 17-3 | `platform/inference/anomaly-detector.yaml` | A predictive (sklearn) KServe InferenceService; the generative copilot is the same kind, differing only in the model block |
| 17-4 | `aiosp/convergence.py` (`check`) | The convergence thesis as an executable test over the manifests |

The printed listings are exact substrings of these files.

## Layout

```
platform/
  inference/      three KServe InferenceServices: anomaly-detector (AIOps,
                  sklearn), churn-model (MLOps, sklearn), incident-copilot
                  (LLMOps, huggingface) - same kind, predictive AND generative
  apps/           Argo CD Applications + the app-of-apps root.yaml
  observability/  the shared OpenTelemetry Collector (Service + config)
aiosp/
  tracing.py      the unified infra + gen_ai trace (Listing 17-1)
  convergence.py  the convergence check (Listing 17-4)
  cost.py         token-to-cost helper (custom app.gen_ai.cost_usd attribute)
labs/             lab1 (unified trace), lab2 (convergence)
tests/            convergence + tracing tests, incl. five negative convergence tests
setup.sh          stand AIOSP up on a local kind cluster (NOT run in CI;
                  needs your own fork of the platform tree, see below)
run_smoke.py      convergence check + unified trace, asserts both
```

## Run

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
export PYTHONPATH=.

python -m aiosp.convergence     # the convergence report
python -m aiosp.tracing         # the unified trace
python run_smoke.py             # both, with assertions
python -m pytest tests/ -q
```

Expected: the convergence check prints "three disciplines, one substrate" and the
unified trace shows the infra span and the gen_ai child span in one trace with
`tokens(in/out)=220/38  cost=$0.000167`.

## Stand it up live (optional; needs Docker + kind, and a GPU for the copilot)

Argo CD reconciles the platform FROM GIT, so the tree must live in a repository
you own. The `repoURL` in `platform/apps/*.yaml` is a marked placeholder
(`https://github.com/YOUR-USERNAME/aiosp-platform.git`) until you substitute
your own:

1. Push this directory to your own Git remote (a public GitHub repo works).
2. `export AIOSP_REPO_URL=https://github.com/<your-username>/aiosp-platform.git`
3. `./setup.sh`: the first run rewrites the placeholder repoURL in
   `platform/apps/` to your remote and stops; commit and push that rewrite.
4. `./setup.sh` again: creates the kind cluster, installs Argo CD and KServe,
   applies the Collector manifest, and hands Argo CD the app-of-apps root.

The script fails loudly if `AIOSP_REPO_URL` is unset or the remote is
unreachable. What you should see once Argo CD reconciles:

```
$ kubectl get applications -n argocd
NAME               SYNC STATUS   HEALTH STATUS
aiosp-root         Synced        Healthy
anomaly-detector   Synced        Healthy
churn-model        Synced        Healthy
incident-copilot   Synced        Progressing
```

`kubectl get inferenceservice -A` shows `anomaly-detector` and `churn-model` with
`READY True`. `anomaly-detector` serves the book's own detector: `setup.sh` runs
Chapter 11's `train.py` (normal rows only) as the `train-detector` Job inside the
image of KServe's `kserve-mlserver` runtime, the one KServe picks for sklearn over
the V2 protocol, so the scikit-learn that writes `model.joblib` is the one that
loads it. The file lands in `./model-store` (gitignored), which the kind node
mounts at `/models` and `platform/storage/detector-model.yaml` exposes as the
`detector-model` PVC behind `storageUri: pvc://detector-model/anomaly-detector`.
`churn-model` pulls KServe's public example sklearn model
(`gs://kfserving-examples/models/sklearn/1.0/model`) as a stand-in until you swap
in your own `storageUri`. `incident-copilot` stays unready without a GPU node; the
convergence claim does not depend on it being up.

Check the detector answers:

```
kubectl port-forward -n aiops svc/anomaly-detector-predictor 18080:80 &
curl -s -X POST localhost:18080/v2/models/anomaly-detector/infer \
  -H 'Content-Type: application/json' \
  -d '{"inputs":[{"name":"input-0","shape":[2,6],"datatype":"FP64",
       "data":[0.1,-0.2,0.0,0.3,-0.1,0.2,3.0,3.1,2.9,3.2,3.0,2.8]}]}'
```

The `predict` output is `[1, -1]`: the normal row is an inlier, the shifted row is
flagged.

## The honest CI-vs-live split

RUN in CI (`ch17-platform` job, one Python 3.12 venv, no cluster/key/GPU):
yamllint over the GitOps manifests; the convergence check (asserts the shared
serving API, the shared Argo delivery loop, and the shared OTLP endpoint, with
predictive AND generative formats present); the unified trace (asserts the infra
and gen_ai spans share one trace, with token usage and a computed cost); and a
five negative tests that the convergence check FAILS when a workload diverges: a divergent
observability endpoint, serving API, or delivery repo, an extra workload, and a workload with
no matching Argo CD Application.

Validation-only, NOT executed (needs a real cluster and, for the LLM, a GPU):
`setup.sh` (stands AIOSP up on kind after the one-time fork-and-substitute above:
Argo CD, KServe, the Collector, the app-of-apps root), the live KServe Hugging
Face / vLLM serving of the Copilot, and
the Backstage portal. The manifests these apply are linted and convergence-checked
in CI; the live deploy is local. Same honesty split as Chapters 11, 13, and 16.

## Pinned versions

Python 3.12; opentelemetry-api/sdk 1.42.1, opentelemetry-semantic-conventions
0.63b1 (matching Chapter 13), PyYAML 6.0.2, pytest 8.4.2, ruff 0.9.10, yamllint
1.35.1. The platform tools referenced in `setup.sh` and the manifests are pinned
to their mid-2026 lines: kind v0.32.0, Argo CD 3.4.4, KServe 0.19.0, Backstage
Helm chart 2.8.2. Re-verify these at copyedit; CNCF tooling moves fast.
