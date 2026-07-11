"""Lab D: async load-test harness for the local MLServer V2 endpoint.

Fires requests at a few concurrency levels against the running anomaly-detector
and prints p50/p99 latency and throughput. A machinery check, not a benchmark:
single-process MLServer on one host, so the numbers are small and synthetic. The
teaching point is the shape, latency climbs and throughput plateaus as concurrency
rises. Run: python loadtest.py --requests 200
"""
from __future__ import annotations

import argparse
import asyncio
import time

import httpx

URL = "http://localhost:8080/v2/models/anomaly-detector/infer"
PAYLOAD = {
    "inputs": [
        {"name": "input-0", "shape": [1, 6], "datatype": "FP64",
         "data": [0.1, -0.2, 0.0, 0.3, -0.1, 0.2]}
    ]
}


def pct(values, q):
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((q / 100.0) * (len(s) - 1)))))
    return s[k]


async def one(client):
    t0 = time.perf_counter()
    r = await client.post(URL, json=PAYLOAD)
    r.raise_for_status()
    return (time.perf_counter() - t0) * 1000.0  # ms


async def run_level(concurrency, total):
    sem = asyncio.Semaphore(concurrency)
    lat = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        async def worker():
            async with sem:
                lat.append(await one(client))
        t0 = time.perf_counter()
        await asyncio.gather(*(worker() for _ in range(total)))
        wall = time.perf_counter() - t0
    return lat, total / wall


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", type=int, default=200)
    args = ap.parse_args()
    await run_level(1, 5)  # warmup
    print(f"{'concurrency':>11} {'p50_ms':>8} {'p99_ms':>8} {'req/s':>9}")
    for c in (1, 4, 16, 32):
        lat, rps = await run_level(c, args.requests)
        print(f"{c:>11} {pct(lat, 50):>8.2f} {pct(lat, 99):>8.2f} {rps:>9.1f}")


if __name__ == "__main__":
    asyncio.run(main())
