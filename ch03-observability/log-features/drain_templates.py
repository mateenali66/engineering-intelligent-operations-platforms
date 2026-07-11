"""Listing 3-4. Drain log-template extraction.

Turns a stream of raw, high-cardinality log lines into a small, fixed set of
templates plus a per-window count vector, which is the log representation that
fed the Paper 5 benchmark (IEEE Access, vol. 14, pp. 93576 to 93608, 2026,
DOI 10.1109/ACCESS.2026.3705430; data at
https://doi.org/10.5281/zenodo.19462083). Drain learns
templates online, so two lines that differ only in their variable parts (an IP,
a request id, a duration) collapse to the same template id.

Pinned dependencies (see README.md):
    python==3.12
    drain3==0.9.11

Run:
    python drain_templates.py
"""
from __future__ import annotations

from collections import Counter

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

# A handful of raw log lines from the OTel Demo's checkout and payment services.
# Note the high-cardinality variable parts: ids, counts, durations.
RAW_LOGS = [
    "order 8f3a1c placed for user 4471 total 219.40",
    "order 2b9d77 placed for user 1188 total 14.99",
    "payment charged card ending 4242 amount 219.40",
    "payment charged card ending 1111 amount 14.99",
    "order 5e1f02 placed for user 9920 total 78.00",
    "checkout failed for user 4471 reason inventory_unavailable",
]


def build_miner() -> TemplateMiner:
    config = TemplateMinerConfig()
    # Similarity threshold: higher means stricter grouping. 0.4 is the library
    # default and works well for structured service logs.
    config.drain_sim_th = 0.4
    config.drain_depth = 4
    return TemplateMiner(config=config)


def extract(raw_logs: list[str]) -> Counter:
    """Mine templates and return a per-template count vector for the window."""
    miner = build_miner()
    counts: Counter = Counter()
    for line in raw_logs:
        result = miner.add_log_message(line)
        template_id = result["cluster_id"]
        counts[template_id] += 1

    print("learned templates:")
    for cluster in miner.drain.clusters:
        print(f"  template {cluster.cluster_id}: {cluster.get_template()}")

    return counts


if __name__ == "__main__":
    vector = extract(RAW_LOGS)
    # The count vector is the per-window log feature joined into the feature
    # table from Listing 3-3 (column family: log_template_<id>_count).
    print("per-window template counts:", dict(vector))
