"""End-to-end smoke test on synthetic data (no Zenodo download, no GPU).

Trains every model family, evaluates them with the harness, and asserts the
qualitative findings the chapter teaches: Isolation Forest and the density model
(DAGMM) separate anomalies (AUC > 0.5), and the evaluation harness reports AUC
before F1. This is what CI runs. The real leaderboard numbers come from the
Paper 5 Zenodo deposit (10.5281/zenodo.19462083), not from this synthetic slice.
"""

from __future__ import annotations

import os

import joblib

from pipeline.data import leakage_safe_split, load_feature_table
from pipeline.deep_models import (
    DAGMM, AutoEncoder, DeepSVDD, TransformerAE, auc_guarding_inversion,
    dagmm_energy_score, deep_svdd_score, reconstruction_score,
    train_autoencoder, train_dagmm, train_deep_svdd,
)
from pipeline.evaluate import evaluate_scores, prevalence_sweep
from pipeline.isoforest import evaluate, fit_isolation_forest
from pipeline.make_synthetic import make_feature_table
import torch


def main():
    os.makedirs("data", exist_ok=True)
    make_feature_table().to_parquet("data/features.parquet", index=False)
    X, y, names = load_feature_table("data/features.parquet")
    ds = leakage_safe_split(X, y, names)
    print(f"features={len(names)} train={ds.X_train.shape} "
          f"test={ds.X_test.shape} prevalence={ds.y_test.mean():.0%}")

    # Isolation Forest baseline.
    iso = fit_isolation_forest(ds.X_train)
    iso_res = evaluate(iso, ds.X_test, ds.y_test)
    print("isolation_forest:", iso_res)
    assert iso_res["auc"] > 0.5, "IF should separate the injected anomalies"

    # Reconstruction transformer-AE, with the inversion guard.
    tae = train_autoencoder(TransformerAE(len(names)), ds.X_train, epochs=15)
    with torch.no_grad():
        x_tr = torch.tensor(ds.X_train, dtype=torch.float32)
        train_err = ((tae(x_tr) - x_tr) ** 2).mean(dim=1).numpy()
    tae_scores = reconstruction_score(tae, ds.X_test, train_err)
    print("transformer_ae:", auc_guarding_inversion(ds.y_test, tae_scores))

    # Plain autoencoder, for contrast.
    ae = train_autoencoder(AutoEncoder(len(names)), ds.X_train, epochs=15)
    with torch.no_grad():
        ae_err = ((ae(x_tr) - x_tr) ** 2).mean(dim=1).numpy()
    ae_scores = reconstruction_score(ae, ds.X_test, ae_err)
    print("autoencoder:", auc_guarding_inversion(ds.y_test, ae_scores))

    # Density-based DAGMM: should separate and never invert.
    dagmm = train_dagmm(DAGMM(len(names)), ds.X_train, epochs=30)
    dg_scores = dagmm_energy_score(dagmm, ds.X_train, ds.X_test)
    dg_res = evaluate_scores(dg_scores, ds.y_test)
    print("dagmm:", dg_res)
    assert dg_res["auc"] > 0.5, "DAGMM energy should separate anomalies"
    assert dg_res["trustworthy"], "AUC should clear the 0.5 gate"

    # Density-based Deep SVDD: distance from center, also never inverts.
    svdd, center = train_deep_svdd(DeepSVDD(len(names)), ds.X_train, epochs=30)
    svdd_scores = deep_svdd_score(svdd, center, ds.X_test)
    svdd_res = evaluate_scores(svdd_scores, ds.y_test)
    print("deep_svdd:", svdd_res)
    assert svdd_res["auc"] > 0.5, "Deep SVDD distance should separate anomalies"

    # The evaluation trap: F1 falls as anomalies get rarer.
    print("dagmm prevalence sweep:", prevalence_sweep(dg_scores, ds.y_test))

    # Persist the deployable detector (the cheap, robust Isolation Forest) with
    # its scaler and column order, so serving/score_service.py can load it.
    os.makedirs("artifacts", exist_ok=True)
    joblib.dump(
        {"model": iso, "scaler": ds.scaler, "feature_names": names},
        "artifacts/detector.joblib",
    )
    print("saved detector -> artifacts/detector.joblib")
    print("smoke: ok")


if __name__ == "__main__":
    main()
