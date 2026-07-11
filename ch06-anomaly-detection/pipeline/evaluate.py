"""Listing 6-4: the evaluation harness (AUC, F1, and a prevalence sweep).

Two rules from the benchmark are baked in here. Verify AUC-ROC > 0.5 before
trusting F1, because a predict-all detector posts F1 = 2p/(1+p) regardless of
skill. And sweep the prevalence, because F1 degrades steeply as anomalies get
rarer even when AUC is flat: a detector that looks fine at 40 percent anomalies
can be near useless at 1 percent.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import f1_score, roc_auc_score


def threshold_f1(scores, y_true, steps=100):
    """Best F1 over a threshold grid, with the chosen threshold."""
    lo, hi = float(scores.min()), float(scores.max())
    best = {"f1": 0.0, "threshold": lo}
    for t in np.linspace(lo, hi, steps):
        f1 = f1_score(y_true, (scores >= t).astype(int), zero_division=0)
        if f1 > best["f1"]:
            best = {"f1": round(float(f1), 3), "threshold": round(float(t), 3)}
    return best


def predict_all_f1(prevalence):
    """The F1 a degenerate predict-all detector earns at this prevalence."""
    return round(2 * prevalence / (1 + prevalence), 3)


def evaluate_scores(scores, y_true):
    """AUC first, then F1, with the predict-all floor for context."""
    auc = float(roc_auc_score(y_true, scores))
    best = threshold_f1(scores, y_true)
    p = float(y_true.mean())
    return {
        "auc": round(auc, 3),
        "f1": best["f1"],
        "predict_all_f1": predict_all_f1(p),
        "prevalence": round(p, 3),
        "trustworthy": auc > 0.5,  # below 0.5, ignore the F1
    }


def prevalence_sweep(scores, y_true, rates=(0.01, 0.05, 0.10, 0.20), seed=42):
    """Subsample anomalies to each target rate and re-measure F1."""
    rng = np.random.default_rng(seed)
    normal = np.flatnonzero(y_true == 0)
    anom = np.flatnonzero(y_true == 1)
    out = {}
    for r in rates:
        k = max(1, int(len(normal) * r / (1 - r)))
        keep = np.concatenate([normal, rng.choice(anom, min(k, len(anom)),
                                                   replace=False)])
        out[r] = threshold_f1(scores[keep], y_true[keep])["f1"]
    return out
