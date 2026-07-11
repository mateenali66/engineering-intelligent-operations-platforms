"""Lab A CI smoke test: serve the anomaly-detector through MLServer (KServe's
sklearn runtime) and assert a V2 Open Inference Protocol response comes back.

Headless: starts MLServer as a subprocess, polls readiness, POSTs to
/v2/models/anomaly-detector/infer, asserts the predictions, then tears down.
No Kubernetes cluster and no GPU. Run: python run_smoke.py
"""
from __future__ import annotations

import subprocess
import sys
import time

import httpx

BASE = "http://localhost:8080"
INFER = f"{BASE}/v2/models/anomaly-detector/infer"
READY = f"{BASE}/v2/models/anomaly-detector/ready"
PAYLOAD = {
    "inputs": [
        {
            "name": "input-0",
            "shape": [2, 6],
            "datatype": "FP64",
            "data": [0.1, -0.2, 0.0, 0.3, -0.1, 0.2,
                     3.0, 3.1, 2.9, 3.2, 3.0, 2.8],
        }
    ]
}


def wait_ready(timeout=60.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(READY, timeout=2.0).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1.0)
    return False


def main():
    subprocess.run([sys.executable, "train.py"], check=True)
    proc = subprocess.Popen(["mlserver", "start", "."])
    try:
        assert wait_ready(), "MLServer did not become ready"
        resp = httpx.post(INFER, json=PAYLOAD, timeout=30.0)
        resp.raise_for_status()
        body = resp.json()
        out = body["outputs"][0]
        assert body["model_name"] == "anomaly-detector"
        assert out["name"] == "predict"
        assert out["shape"] == [2, 1]
        preds = out["data"]
        assert preds[0] == 1, f"normal row should be inlier, got {preds}"
        assert preds[1] == -1, f"shifted row should be anomaly, got {preds}"
        print(f"V2 infer ok: predictions={preds}  (1=inlier, -1=anomaly)")
        print("smoke: ok")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
