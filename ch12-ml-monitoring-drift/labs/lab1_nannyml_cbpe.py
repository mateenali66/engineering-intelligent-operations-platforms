"""Listing 12-2: label-free performance estimation with NannyML CBPE.

The Chapter 6 anomaly-detector is an unsupervised IsolationForest. CBPE
(Confidence-Based Performance Estimation) cannot run on it directly: it needs
CALIBRATED predicted probabilities and hard predictions for a classification
task. So we keep continuity with Chapter 6 by training a small supervised
classifier on the SAME labeled Chapter 6 feature schema, mirroring the
anomaly-detection task (predict the `label` column). This is the cleanest,
honest choice: rather than hand-calibrating IsolationForest decision scores
into probabilities (which CBPE then has to trust), we use a calibrated
LogisticRegression whose probabilities CBPE is designed to consume.

CBPE then estimates ROC AUC on a held-out reference period (where it has labels
to calibrate) and on a later analysis period WITHOUT labels. When the analysis
period drifts, CBPE should estimate a LOWER ROC AUC. We also run NannyML's
multivariate (PCA reconstruction) drift detector on the same data.
"""

from __future__ import annotations

import nannyml as nml
import pandas as pd
from prometheus_client import CollectorRegistry, Gauge
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from make_streams import FEATURE_NAMES, make_streams


def export_estimated_auc(est_auc, registry=None):
    """Export the CBPE estimate as the gauge the chapter alerts on (Section 12.7).

    This is the performance signal the order-of-operations argument pages on, so
    it is the gauge the Alertmanager rule watches (ml_estimated_roc_auc). Drift
    gauges come from the Evidently lab; this one carries label-free performance.
    """
    registry = registry or CollectorRegistry()
    g = Gauge("ml_estimated_roc_auc", "CBPE label-free estimated ROC AUC",
              ["model"], registry=registry)
    g.labels(model="anomaly-detector").set(est_auc)
    return registry


def _score_frame(clf, df):
    """Attach y_pred_proba / y_pred / y_true columns CBPE consumes."""
    out = df.copy()
    out["y_pred_proba"] = clf.predict_proba(df[FEATURE_NAMES])[:, 1]
    out["y_pred"] = clf.predict(df[FEATURE_NAMES])
    out["y_true"] = df["label"]
    return out


def run():
    reference, analysis_stable, analysis_shifted = make_streams()

    # Train the calibrated classifier on a held-out training slice so the
    # reference period CBPE calibrates on is genuinely unseen.
    train = reference.sample(frac=0.5, random_state=42)
    ref_eval = reference.drop(train.index)
    base = LogisticRegression(max_iter=1000)
    clf = CalibratedClassifierCV(base, method="isotonic", cv=3)
    clf.fit(train[FEATURE_NAMES], train["label"])

    ref_scored = _score_frame(clf, ref_eval)
    stable_scored = _score_frame(clf, analysis_stable)
    shifted_scored = _score_frame(clf, analysis_shifted)

    # CBPE: fit on the reference period, estimate without labels on analysis.
    estimator = nml.CBPE(
        y_pred_proba="y_pred_proba",
        y_pred="y_pred",
        y_true="y_true",
        metrics=["roc_auc"],
        chunk_size=300,
        problem_type="classification_binary",
    ).fit(ref_scored)

    def estimated_auc(scored):
        res = estimator.estimate(scored)
        df = res.filter(period="analysis").to_df()
        return float(df[("roc_auc", "value")].mean())

    est_stable = estimated_auc(stable_scored)
    est_shifted = estimated_auc(shifted_scored)

    # Realized AUC (uses the held-back labels) so the chapter can contrast what
    # CBPE estimated against ground truth. CBPE assumes no concept drift, so on
    # a genuine new-fault-mode shift it under-reports: it still flags a drop,
    # but a softer one than reality. That gap is the lesson, and the reason the
    # monitor also runs the multivariate drift detector below.
    realized_stable = float(roc_auc_score(stable_scored["y_true"],
                                          stable_scored["y_pred_proba"]))
    realized_shifted = float(roc_auc_score(shifted_scored["y_true"],
                                           shifted_scored["y_pred_proba"]))

    # Multivariate (PCA reconstruction) drift on the same features.
    drift_calc = nml.DataReconstructionDriftCalculator(
        column_names=FEATURE_NAMES, chunk_size=300
    ).fit(reference[FEATURE_NAMES])
    rc_stable = drift_calc.calculate(analysis_stable[FEATURE_NAMES]).to_df()
    rc_shifted = drift_calc.calculate(analysis_shifted[FEATURE_NAMES]).to_df()
    col = ("reconstruction_error", "value")
    alert = ("reconstruction_error", "alert")
    rc_stable_mean = float(rc_stable[col].mean())
    rc_shifted_mean = float(rc_shifted[col].mean())
    shifted_alerts = int(rc_shifted[alert].sum())

    return {
        "est_auc_stable": est_stable,
        "est_auc_shifted": est_shifted,
        "realized_auc_stable": realized_stable,
        "realized_auc_shifted": realized_shifted,
        "rc_error_stable": rc_stable_mean,
        "rc_error_shifted": rc_shifted_mean,
        "multivariate_alerts_shifted": shifted_alerts,
    }


if __name__ == "__main__":
    pd.set_option("display.width", 120)
    r = run()
    print("CBPE estimated ROC AUC (no labels used on analysis):")
    print(f"  reference->stable  analysis: {r['est_auc_stable']:.3f}  "
          f"(realized {r['realized_auc_stable']:.3f})")
    print(f"  reference->shifted analysis: {r['est_auc_shifted']:.3f}  "
          f"(realized {r['realized_auc_shifted']:.3f})")
    drop = r["est_auc_stable"] - r["est_auc_shifted"]
    print(f"  estimated drop on the shifted period: {drop:.3f}")
    print("Multivariate PCA reconstruction-error drift:")
    print(f"  stable  mean reconstruction error: {r['rc_error_stable']:.3f}")
    print(f"  shifted mean reconstruction error: {r['rc_error_shifted']:.3f}")
    print(f"  drift alerts on shifted chunks: {r['multivariate_alerts_shifted']}")

    from prometheus_client import generate_latest
    registry = export_estimated_auc(r["est_auc_shifted"])
    print("Prometheus exposition (/metrics) excerpt:")
    for line in generate_latest(registry).decode().splitlines():
        if line.startswith("ml_estimated_roc_auc{"):
            print("  " + line)
