"""Send N traces whose spans are split across agents: span 0 of every trace
goes to the first agent, span 1 to the second, and so on. Standard library only,
so it runs in a stock python image inside the cluster."""

import json
import sys
import time
import urllib.request

agents = sys.argv[1].split(",")
prefix = sys.argv[2]  # hex prefix that marks this run's trace IDs
count = int(sys.argv[3])
now = time.time_ns()
for i in range(count):
    trace_id = f"{prefix}{i:08x}".ljust(32, "0")[:32]
    for j, agent in enumerate(agents):
        span = {
            "traceId": trace_id,
            "spanId": f"{j + 1:016x}",
            "name": f"span-{j}",
            "kind": 2,
            "startTimeUnixNano": str(now),
            "endTimeUnixNano": str(now + 1_000_000),
        }
        body = {"resourceSpans": [{
            "resource": {"attributes": [
                {"key": "service.name", "value": {"stringValue": f"svc-{j}"}}]},
            "scopeSpans": [{"spans": [span]}],
        }]}
        req = urllib.request.Request(
            f"http://{agent}:4318/v1/traces",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5).read()
print(f"sent {count} traces x {len(agents)} spans")
