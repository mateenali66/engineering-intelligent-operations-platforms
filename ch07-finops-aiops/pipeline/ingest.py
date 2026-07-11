"""Listing 7-1: ingest a FOCUS billing export and shape it into a time series.

Cost is just another telemetry stream. This loads the FOCUS export, resamples it
into a daily spend series, and lands it in the same lake pattern from Chapter 3.
Two FOCUS details decide whether the series is right: resample on
ChargePeriodStart (the usage window), not BillingPeriodStart (the monthly invoice
window), or the series collapses to one point per month; and sum EffectiveCost
(amortized, after commitments) when the story is about true spend.
"""

from __future__ import annotations

import pandas as pd


def load_daily_spend(path, cost_column="EffectiveCost"):
    """Return a daily spend Series (total across services), indexed by date."""
    df = pd.read_csv(path, parse_dates=["ChargePeriodStart"])
    daily = (
        df.set_index("ChargePeriodStart")[cost_column]
        .resample("D")  # the usage window, not the invoice window
        .sum()
    )
    daily.name = "spend_usd"
    return daily


def per_service_spend(path, cost_column="EffectiveCost"):
    """Return a daily spend Series per service, for allocation and per-service alerts."""
    df = pd.read_csv(path, parse_dates=["ChargePeriodStart"])
    return (
        df.groupby([pd.Grouper(key="ChargePeriodStart", freq="D"), "ServiceName"])
        [cost_column].sum()
    )


if __name__ == "__main__":
    daily = load_daily_spend("data/billing_focus.csv")
    print(f"daily spend series: {len(daily)} days, "
          f"${daily.sum():,.0f} total, peak ${daily.max():,.0f}/day")
    print(daily.tail(7).round(2).to_string())
