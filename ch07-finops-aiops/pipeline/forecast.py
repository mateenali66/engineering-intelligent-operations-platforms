"""Listing 7-3: forecast spend and derive a right-sizing recommendation.

A SARIMAX model captures the weekly seasonality in daily billing data and
projects the next period with a confidence interval. statsmodels is the
CI-friendly choice: pure pip, no CmdStan backend. Prophet and the Temporal Fusion
Transformer (Table 7-2) are richer for strong seasonality and many covariates,
but heavier to run. The right-sizing step turns the forecast into an action:
provision for the forecast plus a safety margin, not for last month's peak.
"""

from __future__ import annotations

import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX


def forecast_spend(daily, steps=14, exclude_anomalies=None, interval=0.80):
    """Fit SARIMAX on the daily series and forecast `steps` days ahead."""
    y = daily.copy()
    if exclude_anomalies is not None:
        # Do not let a known spend spike train the forecast baseline.
        y = y.mask(exclude_anomalies).interpolate()
    model = SARIMAX(
        y,
        order=(1, 1, 1),
        seasonal_order=(1, 0, 0, 7),  # weekly seasonality in daily billing
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    result = model.fit(disp=False)
    fc = result.get_forecast(steps=steps)
    conf = fc.conf_int(alpha=1 - interval)  # columns 'lower y' / 'upper y'
    return pd.DataFrame({
        "forecast": fc.predicted_mean,
        "lower": conf.iloc[:, 0],
        "upper": conf.iloc[:, 1],
    })


def right_size(forecast_df, provisioned_daily, *, horizon_days=7,
               peak_utilization=0.75, max_cut=0.25):
    """Propose a provisioned level for the next decision period.

    Size for the top of the interval, not the mean, and keep that peak at
    or below peak_utilization of capacity so the service keeps headroom for
    its SLO. Cut at most max_cut per change. Spend is a proxy for demand:
    confirm a cut against the service's own load and latency first.
    """
    window = forecast_df.head(horizon_days)  # refit and re-decide each week
    expected_peak = float(window["forecast"].max())
    upper_peak = float(window["upper"].max())
    needed = upper_peak / peak_utilization
    if needed < provisioned_daily:
        action = "downsize"
        recommended = max(needed, provisioned_daily * (1 - max_cut))
    elif expected_peak > provisioned_daily * peak_utilization:
        action, recommended = "scale up", needed  # demand, not just noise
    else:
        action, recommended = "hold", provisioned_daily  # too uncertain to cut
    return {
        "provisioned_daily": round(provisioned_daily, 2),
        "expected_peak": round(expected_peak, 2),
        "upper_peak": round(upper_peak, 2),
        "needed_at_ceiling": round(needed, 2),
        "action": action,
        "recommended_daily": round(recommended, 2),
        # Recovery path: restore the previous level if real daily demand
        # passes the utilization ceiling on the new capacity.
        "rollback_to": round(provisioned_daily, 2),
        "revert_if_demand_over": round(recommended * peak_utilization, 2),
    }


if __name__ == "__main__":
    from cost_anomaly import detect_cost_anomalies
    from ingest import load_daily_spend

    daily = load_daily_spend("data/billing_focus.csv")
    # Exclude detected spend anomalies so the spike does not poison the baseline.
    flags = detect_cost_anomalies(daily)["flagged"]
    fc = forecast_spend(daily, steps=14, exclude_anomalies=flags)
    print(f"14-day forecast mean ${fc['forecast'].mean():,.0f}/day")
    # Provision against the recent typical day, not the anomaly spike.
    print(right_size(fc, provisioned_daily=float(daily.tail(30).median()) * 1.6))
