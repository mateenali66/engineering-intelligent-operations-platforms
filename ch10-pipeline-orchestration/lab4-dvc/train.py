"""The train stage of the DVC pipeline: fit the Chapter 6 detector, write metrics."""
import json

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

df = pd.read_parquet("features.parquet")
y = df.pop("label").to_numpy()
X = df.to_numpy()
# Hold out 30 percent for evaluation, the same split Chapter 9 registered on.
# Never score the gate on training rows: a model measured on the data it was
# fit on reports an inflated metric.
X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.3, stratify=y, random_state=42
)
# Fit on normal rows only, as Chapter 6 requires: a detector that trains on
# the anomalies learns them as normal. The labels mark which rows those are.
clf = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
clf.fit(X_train[y_train == 0])
auc = float(roc_auc_score(y_val, -clf.score_samples(X_val)))
with open("metrics.json", "w") as fh:
    json.dump({"auc": round(auc, 3)}, fh)
print(f"auc={auc:.3f}")
