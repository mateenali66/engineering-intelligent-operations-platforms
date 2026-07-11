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


def forecast_spend(daily, steps=14, exclude_anomalies=None):
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
    conf = fc.conf_int()  # columns are 'lower y' / 'upper y'
    return pd.DataFrame({
        "forecast": fc.predicted_mean,
        "lower": conf.iloc[:, 0],
        "upper": conf.iloc[:, 1],
    })


def right_size(forecast_df, provisioned_daily, safety_margin=0.15):
    """Recommend a provisioned level: forecast peak plus a safety margin."""
    needed = float(forecast_df["forecast"].max()) * (1 + safety_margin)
    headroom = provisioned_daily - needed
    return {
        "provisioned_daily": round(provisioned_daily, 2),
        "recommended_daily": round(needed, 2),
        "daily_headroom": round(headroom, 2),
        "action": "downsize" if headroom > 0 else "scale up",
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
