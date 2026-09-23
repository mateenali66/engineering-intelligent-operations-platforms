"""Promote a registered anomaly-detector version to production (Section 9.7).

Run by the model-quality approver after the Listing 9-3 gate passes on the pull
request. It points the `production` alias at the version and records who
approved it on that version, so the registry holds the last link of the trail:
dataset md5 on the run, run on the version, alias and approver on the version.

    python promote.py --version 1 --approver "model-quality owner"
"""

from __future__ import annotations

import argparse

import mlflow
from mlflow import MlflowClient

MODEL = "anomaly-detector"


def promote(version: str, approver: str) -> None:
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    client = MlflowClient()
    client.set_model_version_tag(MODEL, version, "approved_by", approver)
    client.set_registered_model_alias(MODEL, "production", version)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--approver", required=True)
    args = parser.parse_args()
    promote(args.version, args.approver)
    print(f"{MODEL}@production -> v{args.version} (approved by {args.approver})")


if __name__ == "__main__":
    main()
