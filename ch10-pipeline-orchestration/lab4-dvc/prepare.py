"""The ingest stage of the DVC pipeline: write the Chapter 6 synthetic feature table."""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
rows = np.vstack([rng.normal(0, 1, (800, 6)), rng.normal(3, 1, (80, 6))])
df = pd.DataFrame(rows, columns=[f"f{i}" for i in range(6)])
df["label"] = ([0] * 800) + ([1] * 80)
df.to_parquet("features.parquet")
print(f"wrote features.parquet: {len(df)} rows")
