"""Read each gateway replica's debug log and check that every trace from this
run arrived whole on exactly one replica. Exit 1 if any trace was split."""

import collections
import re
import subprocess
import sys

prefix, spans_per_trace = sys.argv[1], int(sys.argv[2])
pods = subprocess.check_output([
    "kubectl", "-n", "observability", "get", "pods",
    "-l", "app.kubernetes.io/name=gateway-collector",
    "-o", "jsonpath={.items[*].metadata.name}",
]).decode().split()
seen = collections.defaultdict(collections.Counter)
for pod in pods:
    log = subprocess.check_output(
        ["kubectl", "-n", "observability", "logs", pod]).decode()
    for trace_id in re.findall(r"Trace ID\s*:\s*([0-9a-f]{32})", log):
        if trace_id.startswith(prefix):
            seen[trace_id][pod] += 1
split = [t for t, c in seen.items() if len(c) > 1]
whole = [t for t, c in seen.items()
         if len(c) == 1 and sum(c.values()) == spans_per_trace]
per_pod = collections.Counter(p for c in seen.values() for p in c)
print(f"traces: {len(seen)}  whole on one replica: {len(whole)}  "
      f"split: {len(split)}  per replica: {dict(per_pod)}")
sys.exit(1 if split or len(whole) != len(seen) or not seen else 0)
