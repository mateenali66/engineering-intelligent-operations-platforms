# Chapter 7: FinOps Meets AIOps

A cost-intelligence pipeline: ingest a FOCUS billing export, detect spend
anomalies with the Chapter 6 detector, forecast next-period spend, and frame the
result in dollars (savings, ROI, payback, cost per transaction).

| Listing | File | What it is |
|---|---|---|
| Listing 7-1 | `pipeline/ingest.py` | Ingest a FOCUS billing export into a daily spend series |
| Listing 7-2 | `pipeline/cost_anomaly.py` | Cost-anomaly detection reusing the Chapter 6 Isolation Forest |
| Listing 7-3 | `pipeline/forecast.py` | SARIMAX spend forecast and a right-sizing rule that sizes the next week from the 80% upper bound under a 75% utilization ceiling, caps a cut at 25%, and holds when only uncertainty argues against a cut |
| Listing 7-4 | `pipeline/business.py` | Business framing: dollar savings, ROI, payback, unit economics |

`pipeline/make_billing.py` generates a small synthetic FOCUS billing export with
an injected spend spike, so the pipeline runs without any real billing data.
Never put real client billing data in a repo.

## Run it

```bash
pip install -r requirements.txt          # pinned, CI-tested versions
python run_smoke.py                       # ingest -> detect -> forecast -> dollars
# -> flagged 6 spend-anomaly days; peak flagged $3,078/day
#    14-day forecast mean $928/day
#    right-sizing: {... 'action': 'hold', 'recommended_daily': 1724.09, ...}
#    business case (illustrative 20% cut): {'monthly_savings_usd': 9944.54, ... 'payback_months': 1.5}
#    smoke: ok
# The business case uses an assumed 20% cut because the model recommended a
# hold; the cut, implementation cost, and run cost are assumptions.
```

Run commands from this directory (`ch07-finops-aiops/`). The forecaster uses
statsmodels SARIMAX (pure pip, no heavy backend); Prophet and the Temporal Fusion
Transformer are discussed in the chapter (Table 7-2) but kept out of the runnable
code because they are heavier to install. The detector is the same Isolation
Forest from Chapter 6, pointed at cost features.

## Pinned versions

See `requirements.txt`. Tested against scikit-learn 1.9.0, statsmodels 0.14.6,
pandas 2.3.3, numpy 2.4.6. CI runs the same smoke test.

## Note on FOCUS

The synthetic export uses real FOCUS column names (`ChargePeriodStart`,
`EffectiveCost`, `BilledCost`, `ServiceName`). Resample on `ChargePeriodStart`
(the usage window), not `BillingPeriodStart` (the invoice window), and sum
`EffectiveCost` for amortized spend. The same ingest code works on a real
FOCUS export from AWS, Azure, or GCP.
