"""Listing 6-2: an Isolation Forest baseline, end to end.

Isolation Forest (Liu, Ting, and Zhou, ICDM 2008) is the model to reach for
first: no GPU, seconds to train, and in cross-dataset tests it was the strongest
external generalizer in the benchmark. Two scikit-learn sign conventions bite
here, so the code handles both explicitly.
"""

from __future__ import annotations

from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score, roc_auc_score


def fit_isolation_forest(X_train, *, contamination=0.1, seed=42):
    """Train on normal-only rows. y is unused; the model is unsupervised."""
    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=seed,
    )
    model.fit(X_train)
    return model


def anomaly_scores(model, X):
    """Higher means more anomalous.

    score_samples returns LOWER for more anomalous, the opposite of what ROC
    tooling expects, so negate it. This single sign flip is the most common
    Isolation Forest bug.
    """
    return -model.score_samples(X)


def hard_labels(model, X):
    """Map predict's +1/-1 (inlier/outlier) to 0/1 to match ground truth."""
    return (model.predict(X) == -1).astype(int)


def evaluate(model, X_test, y_test):
    scores = anomaly_scores(model, X_test)
    auc = roc_auc_score(y_test, scores)
    f1 = f1_score(y_test, hard_labels(model, X_test))
    return {"auc": round(float(auc), 3), "f1": round(float(f1), 3)}


if __name__ == "__main__":
    from data import leakage_safe_split, load_feature_table

    X, y, names = load_feature_table("data/features.parquet")
    ds = leakage_safe_split(X, y, names)
    model = fit_isolation_forest(ds.X_train)
    print("Isolation Forest:", evaluate(model, ds.X_test, ds.y_test))
