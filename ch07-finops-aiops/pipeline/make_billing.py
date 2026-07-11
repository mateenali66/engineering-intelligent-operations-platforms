"""Generate a small synthetic billing export in FOCUS format.

FOCUS (the FinOps Open Cost and Usage Specification) is the cross-vendor
standard for billing data. This emits spec-shaped columns so the same ingest
code works on a real export. The data is synthetic: never put real client
billing data in the repo. A spend spike is injected on the LLM-inference service
to mirror the runaway-bill story the chapter opens on.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SERVICES = ["Amazon EC2", "Amazon S3", "Amazon RDS", "Amazon Bedrock"]


def make_billing(days=120, seed=42):
    """Return a FOCUS-shaped DataFrame of daily charges per service."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-02-01", tz="UTC")
    rows = []
    for d in range(days):
        day = start + pd.Timedelta(days=d)
        weekday = day.dayofweek
        # Weekly seasonality: weekends are cheaper.
        season = 0.7 if weekday >= 5 else 1.0
        for svc in SERVICES:
            base = {"Amazon EC2": 800, "Amazon S3": 120,
                    "Amazon RDS": 300, "Amazon Bedrock": 60}[svc]
            cost = base * season * (1 + rng.normal(0, 0.05))
            # Injected anomaly: Bedrock (LLM inference) spikes after a launch.
            if svc == "Amazon Bedrock" and 95 <= d <= 99:
                cost *= 40  # the $60/day proof of concept becomes $2,400/day
            rows.append({
                "BillingPeriodStart": start,
                "BillingPeriodEnd": start + pd.Timedelta(days=days),
                "ChargePeriodStart": day,
                "ChargePeriodEnd": day + pd.Timedelta(days=1),
                "ServiceName": svc,
                "BilledCost": round(cost, 2),
                "EffectiveCost": round(cost * 0.85, 2),  # after commitments
                "BillingCurrency": "USD",
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = make_billing()
    df.to_csv("data/billing_focus.csv", index=False)
    print(f"wrote data/billing_focus.csv: {len(df)} charges, "
          f"${df['EffectiveCost'].sum():,.0f} total effective cost")
