"""OPA/Conftest policy gate, reusing the Chapter 4 s3_encryption.rego house rule.

The gate is the last check before a module is allowed through: even after the
scanners are clean, the organization's own Rego policy must pass. Here it
enforces "every S3 bucket must have a server-side encryption configuration."

Conftest evaluates the JSON form of a Terraform plan, not the HCL source, so it
checks what will actually be created. In CI we run it against the RECORDED
plan.json that ships beside each fixture module (see fixtures/*/plan.json),
which keeps the gate headless: no terraform init, no AWS credentials, no
network. The production command that produces a real plan.json is in the
docstring of `run_gate`.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .scanners import conftest_bin

_REPO = Path(__file__).resolve().parent.parent
POLICY_DIR = _REPO / "policy"


@dataclass
class GateResult:
    passed: bool
    failures: list[str]


def run_gate(plan_json: str | Path, policy_dir: str | Path = POLICY_DIR) -> GateResult:
    """Run Conftest with the Rego policy against a Terraform plan JSON.

    Production (NOT in CI, needs terraform + provider auth):
        terraform -chdir=<module> init -backend=false
        terraform -chdir=<module> plan -out tfplan
        terraform -chdir=<module> show -json tfplan > plan.json
        # then call run_gate("plan.json")

    In CI we pass the recorded fixtures/<rev>/plan.json instead.
    """
    proc = subprocess.run(
        [conftest_bin(), "test", str(plan_json),
         "--policy", str(policy_dir), "--output", "json"],
        capture_output=True, text=True, check=False,
    )
    # Conftest exits non-zero on a policy failure; parse JSON either way.
    failures: list[str] = []
    out = proc.stdout.strip()
    if out:
        for block in json.loads(out):
            for f in block.get("failures", []):
                failures.append(f.get("msg", ""))
    return GateResult(passed=(len(failures) == 0), failures=failures)
