"""Listing 9-3 (companion): block promotion when a metric regresses.

A GitHub Actions job fails when any step exits non-zero, so the validation gate
is just a script that exits 1 on a regression. No special action is needed. Keep
the comparison direction right: higher-is-better metrics use this inequality;
flip it for loss or latency.
"""

from __future__ import annotations

import json
import sys

TOLERANCE = 0.01  # allow tiny run-to-run noise; tune per dataset


def main():
    with open("metrics/current.json") as f:
        current = json.load(f)["auc"]
    with open("metrics/baseline.json") as f:
        baseline = json.load(f)["auc"]

    if current < baseline - TOLERANCE:
        print(f"REGRESSION: auc {current:.4f} < baseline {baseline:.4f}")
        sys.exit(1)

    print(f"PASS: auc {current:.4f} >= baseline {baseline:.4f}")


if __name__ == "__main__":
    main()
