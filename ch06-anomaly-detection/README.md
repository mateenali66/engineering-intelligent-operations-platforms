# Chapter 6: Building Anomaly Detection Pipelines

A complete anomaly-detection pipeline on the Chapter 3 feature table: load and
split the data without leaking labels, train the model families, evaluate them
honestly, and serve the chosen detector into the Chapter 5 loop.

| Listing | File | What it is |
|---|---|---|
| Listing 6-1 | `pipeline/data.py` | Load the parquet feature table and make a leakage-safe, normal-only split |
| Listing 6-2 | `pipeline/isoforest.py` | Isolation Forest baseline, with the two scikit-learn sign conventions handled |
| Listing 6-3 | `pipeline/deep_models.py` | Transformer autoencoder, the reconstruction-collapse guard, and DAGMM density scoring |
| Listing 6-4 | `pipeline/evaluate.py` | Evaluation harness: AUC gate, predict-all floor, prevalence sweep |
| Listing 6-5 | `serving/score_service.py` | FastAPI scoring service that loads the persisted detector and feeds the Chapter 5 confidence gate |

`pipeline/make_synthetic.py` generates a small feature table with the Chapter 3
schema so everything runs without the 58 MB Zenodo download or a GPU. The real
benchmark data is mirrored at Zenodo concept DOI 10.5281/zenodo.19462083; the
leaderboard numbers in the chapter reproduce from that deposit, not from the
synthetic slice.

## Run it

```bash
pip install -r requirements.txt          # pinned, CI-tested versions
python run_smoke.py                       # train every model on the synthetic slice
# -> isolation_forest: {'auc': 0.992, 'f1': 0.852}
#    transformer_ae: {'auc': 0.995, 'inverted': False}
#    autoencoder: {'auc': 0.997, 'inverted': False}
#    dagmm: {'auc': 0.577, ..., 'trustworthy': True}
#    deep_svdd: {'auc': 0.94, ..., 'trustworthy': True}
#    saved detector -> artifacts/detector.joblib
#    smoke: ok

# serve the detector persisted above (loaded from artifacts/detector.joblib on startup)
uvicorn serving.score_service:app --host 0.0.0.0 --port 8000
curl -s localhost:8000/healthz            # -> {"ready":true}; false means no artifact loaded

# score one window of features; an anomalous window (high memory/latency/error) scores ~0.61
curl -s -X POST localhost:8000/score -H 'Content-Type: application/json' -d '{
  "service_name": "payment",
  "features": {
    "cpu_utilization_mean": 0.4, "cpu_utilization_p95": 0.9,
    "memory_working_set_bytes_mean": 3.8, "memory_working_set_bytes_p95": 4.2,
    "request_latency_ms_mean": 3.5, "request_latency_ms_p95": 4.0,
    "request_rate_mean": 0.2, "request_rate_p95": 0.7,
    "error_rate_mean": 3.6, "error_rate_p95": 4.1, "sample_count": 20
  }
}'
# -> {"service_name":"payment","anomaly_score":0.61}   (a quiet window scores ~0.37)
```

Run commands from this directory (`ch06-anomaly-detection/`). `run_smoke.py`
writes the synthetic table to `data/features.parquet`, trains Isolation Forest,
the autoencoders, and DAGMM, runs the evaluation harness, asserts the
qualitative findings the chapter teaches, and persists the deployable Isolation
Forest detector (model, scaler, and column order) to `artifacts/detector.joblib`.
The scoring service loads that artifact on startup; set `DETECTOR_ARTIFACT` to
override the path. Until an artifact is loaded, `/healthz` reports
`{"ready": false}` and `/score` returns HTTP 503 rather than crashing.

## Pinned versions

See `requirements.txt`. Tested against scikit-learn 1.9.0, torch 2.12.1,
fastapi 0.138.0, pydantic 2.12.5, numpy 2.4.6, pandas 2.3.3, pyarrow 24.0.0.
CI installs CPU-only torch and runs the same smoke test.

## Note on the synthetic data

The synthetic anomalies are cleanly separable, so on that slice the
reconstruction autoencoders do NOT collapse and Isolation Forest scores very
high. That is expected. The reconstruction-collapse failure mode, the DAGMM win,
and the mean-aggregation result are properties of the real OpenTelemetry data
(reproduce from Zenodo). The synthetic smoke verifies the machinery runs and the
guards fire, not the leaderboard ranking.
