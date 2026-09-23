"""Backtest the one-week forecast interval that right_size sizes from (Section 7.4).

Refit the SARIMAX model every 7 days on the history so far, forecast the next 7
days, and count how often actual spend on a normal (non-anomalous) day landed
above that day's 80 percent upper bound. An 80 percent two-sided interval
promises about one exceedance in ten. The first refit waits for 28 days, four
weekly cycles, the minimum a weekly-seasonal model needs.
"""

from __future__ import annotations

import warnings

from statsmodels.tsa.statespace.sarimax import SARIMAX


def backtest_upper_bound(daily, flags, *, first_fit=28, horizon=7, interval=0.80):
    """Return (exceedances, normal_days) for the one-week upper bound."""
    y = daily.mask(flags).interpolate()  # anomalies never train the baseline
    hits = days = 0
    for end in range(first_fit, len(y) - horizon, horizon):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = SARIMAX(
                y.iloc[:end],
                order=(1, 1, 1),
                seasonal_order=(1, 0, 0, 7),
                enforce_stationarity=False,
                enforce_invertibility=False,
            ).fit(disp=False)
        upper = result.get_forecast(horizon).conf_int(alpha=1 - interval).iloc[:, 1]
        actual = daily.iloc[end:end + horizon].to_numpy()
        normal = ~flags.iloc[end:end + horizon].to_numpy()
        hits += int((actual[normal] > upper.to_numpy()[normal]).sum())
        days += int(normal.sum())
    return hits, days


if __name__ == "__main__":
    from cost_anomaly import detect_cost_anomalies
    from ingest import load_daily_spend

    daily = load_daily_spend("data/billing_focus.csv")
    flags = detect_cost_anomalies(daily)["flagged"]
    hits, days = backtest_upper_bound(daily, flags)
    print(f"backtest: actual above the one-week 80% upper bound on {hits} of "
          f"{days} normal days ({hits / days:.0%}; the interval promises about 10%)")
