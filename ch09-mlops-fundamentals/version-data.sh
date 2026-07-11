#!/usr/bin/env bash
# Listing 9-1: version a dataset with DVC, backed by a local remote.
# Run inside a Git repo. DVC tracks a small pointer file in Git while the dataset
# bytes live in a separate remote, so Git stays small and the data stays versioned.
# The remote here is a local directory, so the whole leg runs with no extra
# services; in production you swap it for S3 or MinIO (one line, shown at the end).
set -euo pipefail

# 0. Generate the dataset (same distribution train.py uses, so the bytes are
#    reproducible). Skip this if you already have data/telemetry.csv.
python generate_data.py

# 1. Initialize DVC in the Git repo (creates .dvc/ and .dvcignore).
dvc init
git add .dvc .dvcignore
git commit -m "Initialize DVC"

# 2. Track the dataset. This writes data/telemetry.csv.dvc, the pointer Git keeps.
dvc add data/telemetry.csv
git add data/telemetry.csv.dvc data/.gitignore
git commit -m "Track telemetry dataset with DVC"

# 3. Add a default remote. A local directory needs no object store to run this leg.
dvc remote add -d localremote /tmp/aiosp-dvcstore
git add .dvc/config
git commit -m "Configure DVC remote"

# 4. Push the dataset bytes to the remote. The .dvc pointer in Git resolves to it.
dvc push

# In production, point the remote at S3-compatible object storage (MinIO or AWS S3)
# instead of a local directory. Credentials go to .dvc/config.local via
# `dvc remote modify --local`, which is git-ignored, never the tracked config:
#   dvc remote add -d minio s3://aiosp/dvcstore
#   dvc remote modify minio endpointurl http://localhost:9000
#   dvc remote modify --local minio access_key_id minioadmin
#   dvc remote modify --local minio secret_access_key minioadmin
