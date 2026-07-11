# Chapter 12: ML Monitoring and Drift Detection

Code for Chapter 12. The running example is a monitoring sidecar for the Chapter
6/9/10/11 `anomaly-detector` (a scikit-learn IsolationForest). The labs answer
the production question the prior chapters leave open: once the detector is
served, how do you know it is still working when no fresh labels arrive?

Listing numbers follow order of appearance in the chapter; the files are named by
tool, so the numbers and file names intentionally do not line up.

| Listing | File | Runs in CI? |
|---|---|---|
| 12-1 | `labs/lab3_river_adwin.py` | yes (River ADWIN streaming change-point detection) |
| 12-2 | `labs/lab1_nannyml_cbpe.py` | yes (NannyML CBPE label-free performance estimation + multivariate drift) |
| 12-3 | `labs/lab2_evidently_prometheus.py` | yes (Evidently drift report exported as Prometheus gauges) |
| 12-4 | `labs/lab4_phoenix_genai_eval.py` | no (validation-only: needs a Phoenix server + an LLM API key, like Ch11's vLLM path) |
| 12.7 | `alerts/ml-monitoring-rules.yaml`, `grafana/ml-monitoring-dashboard.json` | yamllint + promtool check + promtool unit tests (alerts), JSON-parse (dashboard), selector cross-check in `run_smoke.py` |

`labs/make_streams.py` generates three slices in the Chapter 6 feature-table
schema with the same seeding style (`numpy.default_rng(42)`): a stable reference
period, a stable analysis period, and a shifted analysis period (a new fault
mode plus covariate drift). The same generator feeds all three batch labs; a
1-D projection feeds the streaming detector.

## The honest CBPE choice (Listing 12-2)

The Chapter 6 detector is an UNSUPERVISED IsolationForest. NannyML's CBPE needs
calibrated predicted probabilities and hard predictions for a classification
task, which IsolationForest does not produce. Rather than hand-calibrate its
decision scores into probabilities (which CBPE would then have to trust), the
lab trains a small calibrated `LogisticRegression` on the SAME labeled Chapter 6
features, mirroring the detection task. That keeps schema continuity and gives
CBPE the probabilities it is designed for.

CBPE then estimates ROC AUC on a reference period and on a later analysis period
WITHOUT labels. The lab also prints the realized AUC (using held-back labels) so
you can see the gap: under a genuine new-fault-mode concept drift, CBPE flags a
drop but UNDER-reports it (CBPE assumes no concept drift). That gap is the
chapter's lesson, and the reason the sidecar also runs multivariate drift and
ADWIN, and backfills labels before retraining.

## Run it (no server, no GPU, no cluster)

```bash
cd labs
python -m venv .venv && source .venv/bin/activate   # use Python 3.12
pip install -r requirements.txt
python run_smoke.py
# -> lab1 CBPE: est stable=0.998 est shifted=0.980 (realized 0.997 -> 0.633) multivariate_alerts=10
#    lab2 Evidently: drifted_columns=10 drift_share=1.00
#    lab3 ADWIN: true_change=1000 first_detection=1023
#    wiring: 5 alert/panel selectors match exported series
#    smoke: ok
```

Run any lab on its own from `labs/` (e.g. `python lab1_nannyml_cbpe.py`).

## Pinned versions (verified mid-2026)

All three runnable labs resolve and run in ONE Python 3.12 environment:
`nannyml==0.13.1`, `evidently==0.7.21`, `river==0.25.0`,
`prometheus-client==0.25.0`, `scikit-learn==1.9.0` (same pin as Ch6/Ch9/Ch11),
sharing `pandas==3.0.3`, `numpy==2.5.0`, `scipy==1.18.0` with no conflicting
pins.

**Python 3.12, not 3.14.** NannyML 0.13.1 pins `python <3.13`, the same kind of
version pin Chapter 11 hit with MLServer. River needs `>=3.11` and Evidently
`>=3.10`, so 3.12 is the single version satisfying all three.

The Prometheus export uses the `prometheus-client` library only. No Prometheus
server is needed: the lab sets gauge values and (optionally) serves them on a
`127.0.0.1` endpoint you can curl, then tears it down. Every gauge carries a
`model="anomaly-detector"` label; that label is the series identity the alert
rule and the dashboard select on. The alert rule and Grafana dashboard in
`alerts/` and `grafana/` are the production wiring (Section 12.7). CI guards it
three ways: `promtool check rules` validates syntax,
`promtool test rules alerts/ml-monitoring-rules.test.yaml` replays synthetic
series carrying the exported label set and asserts both alerts fire, and
`run_smoke.py` cross-checks every alert/panel selector against the gauges the
labs actually export, so a selector that is valid but matches no series (a dead
alert, an empty panel) fails CI. The dashboard is also JSON-parsed.

## Note on the synthetic data

The synthetic slices make the drift cleanly visible so the machinery and the
assertions run deterministically in CI. The qualitative findings (CBPE
estimating a drop, Evidently flagging columns, ADWIN locating the change point)
hold; the exact magnitudes are properties of this synthetic slice, not the real
OpenTelemetry benchmark (Zenodo concept DOI 10.5281/zenodo.19462083).
