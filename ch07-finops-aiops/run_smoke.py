"""End-to-end FinOps pipeline on synthetic billing data (CI entry point).

Ingest a FOCUS export, detect the injected spend spike with the Chapter 6
detector, forecast next-period spend, and frame the result in dollars. Asserts
the qualitative outcomes the chapter teaches: the spike is flagged, the forecast
runs, and the business case produces a finite payback.
"""

from __future__ import annotations

import os

from pipeline.business import SavingsCase, business_case, unit_economics
from pipeline.cost_anomaly import detect_cost_anomalies
from pipeline.forecast import forecast_spend, right_size
from pipeline.ingest import load_daily_spend
from pipeline.make_billing import make_billing


def main():
    os.makedirs("data", exist_ok=True)
    make_billing().to_csv("data/billing_focus.csv", index=False)
    daily = load_daily_spend("data/billing_focus.csv")
    print(f"daily spend: {len(daily)} days, ${daily.sum():,.0f} total")

    # Detect the injected Bedrock spike with the Chapter 6 Isolation Forest.
    result = detect_cost_anomalies(daily)
    flagged = result[result["flagged"]]
    print(f"flagged {len(flagged)} spend-anomaly days; "
          f"peak flagged ${flagged['spend'].max():,.0f}/day")
    assert len(flagged) > 0, "the injected spend spike should be flagged"

    # Forecast, excluding the spike so it does not poison the baseline.
    fc = forecast_spend(daily, steps=14, exclude_anomalies=result["flagged"])
    print(f"14-day forecast mean ${fc['forecast'].mean():,.0f}/day")
    assert fc["forecast"].notna().all(), "forecast should produce values"

    rs = right_size(fc, provisioned_daily=float(daily.tail(30).median()) * 1.6)
    print("right-sizing:", rs)

    # Frame in dollars, not RMSE. The savings are model-derived: baseline and
    # optimized spend are the right-sizing output (provisioned and recommended
    # daily levels) carried over 30 days, so the daily headroom becomes the
    # monthly saving. Implementation and run costs are illustrative assumptions,
    # not model output; keep the two apart.
    case = SavingsCase(monthly_baseline_usd=rs["provisioned_daily"] * 30,
                       monthly_optimized_usd=rs["recommended_daily"] * 30,
                       implementation_usd=15_000, monthly_run_usd=400)
    bc = business_case(case)
    print("business case:", bc)
    print("cost per transaction $",
          unit_economics(rs["recommended_daily"] * 30, 2_400_000))
    assert bc["payback_months"] < float("inf"), "payback should be finite"
    print("smoke: ok")


if __name__ == "__main__":
    main()
