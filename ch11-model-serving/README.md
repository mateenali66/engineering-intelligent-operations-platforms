# Chapter 11: Model Serving and Inference at Scale

Code for Chapter 11. The running example is the convergence proof: the Chapter 6/9/10
`anomaly-detector` (a scikit-learn IsolationForest) and a generative LLM served through
the SAME KServe `InferenceService`, differing only in the runtime and the model reference.

The honest reality of serving is that a real KServe deploy needs a Kubernetes cluster
and an LLM needs a GPU, neither available in CI. So the repo splits into what runs
headless and what is statically validated.

| Listing | File | Runs in CI? |
|---|---|---|
| 11-1 | `manifests/inferenceservice-sklearn.yaml` | yamllint only (needs a KServe + Knative cluster to apply) |
| 11-2 | `manifests/inferenceservice-vllm-llm.yaml` | yamllint only (needs a GPU node) |
| 11-3 | `serving/loadtest.py` | yes (load test against the local server) |
| 11-4 | `manifests/inferenceservice-canary.yaml` | yamllint only (needs a cluster) |

The serving runtime under the sklearn `InferenceService` is MLServer, so `serving/`
runs the exact same KServe V2 Open Inference Protocol locally, with no cluster, and CI
asserts it. That is the live, headless payoff; the manifests are the production form.

## Pinned versions (verified June 2026)

- `mlserver==1.7.1`, `mlserver-sklearn==1.7.1` (KServe's default runtime for the V2 protocol)
- `scikit-learn==1.9.0`, `numpy==2.4.6`, `httpx==0.28.1` (same pins as Ch6/Ch9, so the model loads with no skew)
- Manifests target KServe `serving.kserve.io/v1beta1` (KServe v0.19.x); the vLLM one uses the Hugging Face runtime, whose backend is vLLM 0.23.x.

Lab A and Lab D pin **Python 3.12**, not 3.14: MLServer 1.7.1's uvloop/asyncio stack
breaks the parallel worker bootstrap on 3.14. `settings.json` sets `parallel_workers: 0`
so inference runs in-process (correct for a single-model lab and required on this stack).

## Run the local serving path (no cluster, no GPU)

```bash
cd serving
python -m venv .venv && source .venv/bin/activate   # use Python 3.12
pip install -r requirements.txt
python run_smoke.py        # trains, starts MLServer, POSTs a V2 infer, asserts [1, -1]
```

To load test it by hand, start the server and run the harness in another shell:

```bash
python train.py && mlserver start .          # terminal 1
python loadtest.py --requests 200            # terminal 2: prints p50/p99 vs throughput
```

The V2 request and response shape:

```bash
curl -s http://localhost:8080/v2/models/anomaly-detector/infer \
  -H "Content-Type: application/json" \
  -d '{"inputs":[{"name":"input-0","shape":[2,6],"datatype":"FP64",
       "data":[0.1,-0.2,0.0,0.3,-0.1,0.2, 3.0,3.1,2.9,3.2,3.0,2.8]}]}'
# -> outputs[0].data == [1, -1]   (1 = inlier, -1 = anomaly, the Chapter 6 sign convention)
```

## From the registry to storageUri (the Chapter 9 handoff)

The `storageUri` in the manifests points at object storage, not at the MLflow registry,
so the model registered in Chapter 9 has to travel there first. Run these two commands
in the Chapter 9 lab environment (it has `mlflow`), where `anomaly-detector` is registered:

```bash
# KServe's sklearn runtime loads a model.joblib, but MLflow 3 stores the sklearn
# flavor as model.skops, so repackage the estimator once.
python -c "import mlflow.sklearn, joblib; \
    joblib.dump(mlflow.sklearn.load_model('models:/anomaly-detector/1'), 'model.joblib')"

# Upload the one file to object storage the cluster can reach (MinIO in the lab).
mc cp model.joblib myminio/aiosp-models/anomaly-detector/1/model.joblib
```

`storageUri: "s3://aiosp-models/anomaly-detector/1"` then resolves to that object, and
KServe's storage-initializer pulls it into the pod. A private bucket needs credentials: put
the MinIO or S3 access key in a Kubernetes Secret and reference it from the predictor's
service account. A reader without a registry can point `storageUri` at KServe's public
sample model (`gs://kserve-examples/models/sklearn/1.0/model`), the fallback in the manifest.

Verification split: the repackage half is execution-verified
(it produces a `model.joblib` that predicts `[1, -1]` on the chapter payload, the same
result the local MLServer lab returns); the MinIO upload and cluster `storageUri` pull are
statically verified, because they need a cluster.

## Apply the manifests (needs a real cluster)

The three `manifests/` files are production KServe `InferenceService` resources. They are
not applied in CI. On a cluster with KServe and Knative installed:

```bash
kubectl create namespace kserve-test
kubectl apply -f manifests/inferenceservice-sklearn.yaml   # CPU, scale-to-zero
kubectl apply -f manifests/inferenceservice-vllm-llm.yaml  # needs an nvidia.com/gpu node
kubectl apply -f manifests/inferenceservice-canary.yaml    # 90/10 canary
```

## CI

- `ch11-serving` (gating, headless, Python 3.12): ruff, then `run_smoke.py` (Lab A: serve
  + assert the V2 response), then the load harness (Lab D: assert it prints a p50/p99 table).
- `yaml-lint` (gating): the three KServe manifests are validated for YAML structure. They
  are real `v1beta1` schemas but are not applied, because Labs B and E need a cluster and
  Lab C needs a GPU.
