"""Listing 14-1 (RUNS IN CI): generate + scan.

generate() is a STUBBED LLM: it returns a recorded, realistic-but-INSECURE
Terraform module (rev1_insecure: a public-read S3 bucket with no KMS encryption, no
versioning, no logging, no public-access block), exactly the output Chapter 4
and Chapter 14 warn about. There is no live model call and no API key.

Then the REAL scanners run: Checkov 3.3.1 and Trivy 0.71.1 config, in PARALLEL.
We parse their findings and report the vulnerability count by severity. The
generate step is honestly a recorded fixture; the scanning is real.

Run:
    python labs/lab1_generate_scan.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from iacgen import generate as gen
from iacgen.scanners import scan_parallel


def main() -> None:
    prompt = "a secure S3 bucket Terraform module for telemetry exports"
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp) / "module"
        # STUBBED LLM: recorded insecure module, not a live generation.
        module = gen.generate(prompt, workdir)
        print(f"generate() [stubbed LLM]: {prompt!r}")
        print(f"  -> recorded module at {module} ({module.name} fixture)")

        # REAL scanners, run concurrently.
        result = scan_parallel(module)

        counts = result.counts_by_severity()
        print("\nscan (Checkov 3.3.1 + Trivy 0.71.1, parallel):")
        print(f"  total findings : {len(result.findings)}")
        print("  by severity    : "
              + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        print(f"  blocking       : {len(result.blocking)} (build-failing)")

        by_scanner: dict[str, int] = {}
        for f in result.findings:
            by_scanner[f.scanner] = by_scanner.get(f.scanner, 0) + 1
        print("  by scanner     : "
              + ", ".join(f"{k}={v}" for k, v in sorted(by_scanner.items())))

        print("\nsample findings:")
        for f in result.findings[:6]:
            print(f"  [{f.scanner:7}] {f.rule_id:14} {f.severity:8} {f.title}")

        assert result.has_blocking, \
            "the recorded insecure module must produce blocking findings"


if __name__ == "__main__":
    main()
