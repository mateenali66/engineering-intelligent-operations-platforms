"""End-to-end smoke test for Chapter 12 labs 1-3 (headless, no server, no GPU).

Runs the three runnable monitoring labs and asserts the outcomes the chapter
teaches:

  Lab 1 (NannyML CBPE) : estimates a LOWER ROC AUC on the shifted period than on
                         the stable one, and the multivariate detector alerts.
  Lab 2 (Evidently)    : flags drift (drifted columns > 0) and the Prometheus
                         gauges carry those values with the model label.
  Lab 3 (River ADWIN)  : detects a change point AFTER the injected shift.

It then cross-checks the production wiring: every ml_* selector in the 12.7
alert rules and Grafana dashboard must match a series the labs actually export,
metric name AND labels. promtool and yamllint validate syntax; only this check
catches a selector that is valid but matches nothing (a dead alert, an empty
panel).

This is what CI runs. Prints "smoke: ok" when every assertion holds.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from prometheus_client import generate_latest

import lab1_nannyml_cbpe
import lab2_evidently_prometheus
import lab3_river_adwin

WIRING_DIR = Path(__file__).resolve().parent.parent
_SELECTOR = re.compile(r"([a-zA-Z_:][a-zA-Z0-9_:]*)\{([^}]*)\}")
_LABEL_PAIR = re.compile(r'(\w+)="([^"]*)"')


def _exported_series(exposition):
    """Map metric name -> list of label dicts present in the exposition."""
    series = {}
    for line in exposition.splitlines():
        if not line or line.startswith("#"):
            continue
        match = _SELECTOR.match(line)
        if match:
            name, labels = match.group(1), dict(_LABEL_PAIR.findall(match.group(2)))
        else:
            name, labels = line.split(" ", 1)[0], {}
        series.setdefault(name, []).append(labels)
    return series


def check_wiring(exposition):
    """Assert every ml_* selector in the alert rules and dashboard matches an
    exported series. Skips quietly if the wiring files are not alongside labs/."""
    rules_path = WIRING_DIR / "alerts" / "ml-monitoring-rules.yaml"
    dash_path = WIRING_DIR / "grafana" / "ml-monitoring-dashboard.json"
    if not (rules_path.exists() and dash_path.exists()):
        print("wiring check skipped: alerts/ and grafana/ not found")
        return
    exprs = re.findall(r"expr:\s*(.+)", rules_path.read_text())
    dashboard = json.loads(dash_path.read_text())
    exprs += [t["expr"] for panel in dashboard["panels"] for t in panel["targets"]]
    series = _exported_series(exposition)
    checked = 0
    for expr in exprs:
        for name, raw_labels in _SELECTOR.findall(expr):
            if not name.startswith("ml_"):
                continue
            wanted = dict(_LABEL_PAIR.findall(raw_labels))
            assert any(
                wanted.items() <= exported.items() for exported in series.get(name, [])
            ), f"selector {name}{{{raw_labels}}} matches no exported series"
            checked += 1
    assert checked > 0, "no ml_* selectors found to check"
    print(f"wiring: {checked} alert/panel selectors match exported series")


def main():
    # Lab 1: label-free performance estimation.
    r1 = lab1_nannyml_cbpe.run()
    print(f"lab1 CBPE: est stable={r1['est_auc_stable']:.3f} "
          f"est shifted={r1['est_auc_shifted']:.3f} "
          f"(realized {r1['realized_auc_stable']:.3f} -> "
          f"{r1['realized_auc_shifted']:.3f}) "
          f"multivariate_alerts={r1['multivariate_alerts_shifted']}")
    assert r1["est_auc_shifted"] < r1["est_auc_stable"], \
        "CBPE should estimate lower performance on the shifted period"
    assert r1["multivariate_alerts_shifted"] > 0, \
        "multivariate drift should alert on the shifted period"
    # The estimated-AUC gauge is the one the Alertmanager rule in 12.7 watches.
    auc_registry = lab1_nannyml_cbpe.export_estimated_auc(r1["est_auc_shifted"])
    assert "ml_estimated_roc_auc{" in generate_latest(auc_registry).decode(), \
        "the CBPE estimate should be exported as the ml_estimated_roc_auc gauge"

    # Lab 2: Evidently drift -> Prometheus gauges.
    metrics, registry = lab2_evidently_prometheus.run()
    print(f"lab2 Evidently: drifted_columns={metrics['drifted_columns']} "
          f"drift_share={metrics['drift_share']:.2f}")
    assert metrics["drifted_columns"] > 0, "Evidently should flag drifted columns"
    exposition = generate_latest(registry).decode()
    assert 'ml_drift_share{model="anomaly-detector"}' in exposition, \
        "drift gauges should carry the model label the 12.7 alert rule selects on"

    # Lab 3: River ADWIN streaming change detection.
    r3 = lab3_river_adwin.run()
    print(f"lab3 ADWIN: true_change={r3['true_change_index']} "
          f"first_detection={r3['first_detection']}")
    assert r3["first_detection"] is not None, "ADWIN should detect a change point"
    assert r3["first_detection"] >= r3["true_change_index"], \
        "ADWIN should flag the change after the injected shift, not before"

    # Wiring: every ml_* selector in the alert rules and dashboard must match
    # a series the labs export, name and labels both.
    check_wiring(generate_latest(auc_registry).decode() + exposition)

    print("smoke: ok")


if __name__ == "__main__":
    main()
