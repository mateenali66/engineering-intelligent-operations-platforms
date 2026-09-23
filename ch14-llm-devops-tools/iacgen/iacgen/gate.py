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
    # Conftest exits 1 on a policy failure; parse JSON either way. Fail closed:
    # any other exit code, unreadable output, or a non-zero exit with no
    # recorded failure means the policy was not evaluated, so the gate fails.
    failures: list[str] = []
    out = proc.stdout.strip()
    try:
        for block in json.loads(out) if out else []:
            for f in block.get("failures", []):
                failures.append(f.get("msg", ""))
    except json.JSONDecodeError:
        return GateResult(passed=False, failures=["conftest output was not JSON"])
    if proc.returncode not in (0, 1) or (proc.returncode == 1 and not failures):
        return GateResult(passed=False,
                          failures=[f"conftest exited {proc.returncode}"])
    if not out:
        return GateResult(passed=False, failures=["conftest produced no output"])
    return GateResult(passed=(len(failures) == 0), failures=failures)


def plan_summary(plan_json: str | Path) -> list[str]:
    """One line per planned resource change, the diff a reviewer approves.

    The scanners judge whether a module is safe; only the plan shows whether it
    is the change that was asked for. In CI this reads the recorded fixture,
    which is trimmed to the resources the policy checks; in production pass the
    real `terraform show -json` output and every change appears.
    """
    data = json.loads(Path(plan_json).read_text())
    lines = []
    for change in data.get("resource_changes", []):
        actions = "/".join(change.get("change", {}).get("actions", []))
        lines.append(f"{actions:<8} {change.get('address', '?')}")
    return lines

