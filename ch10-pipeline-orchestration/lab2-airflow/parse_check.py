"""CI gate for Listing 10-2: parse the DAGs without a scheduler or a database.

A DagBag parse catches every import and syntax error a reader would hit, and needs no
running Airflow. It is the cheap, deterministic check the chapter promises.
"""
from airflow.models import DagBag

bag = DagBag("dags", include_examples=False)
assert bag.import_errors == {}, bag.import_errors
assert "refresh_features" in bag.dags
assert "retrain_anomaly_detector" in bag.dags
print("DagBag ok: both DAGs parsed with no import errors")
