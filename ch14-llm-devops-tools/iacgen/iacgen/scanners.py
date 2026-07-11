"""Scanner adapters: run Checkov and Trivy in PARALLEL and normalize findings.

These are the REAL scanners (Checkov 3.3.1, Trivy 0.71.1). The functions shell
out to the pinned binaries, parse their JSON, and return a normalized list of
Finding records so the loop and the SARIF writer do not care which scanner
produced a result.

Tool-resolution order, so the same code runs locally and in CI:
  CHECKOV_BIN / TRIVY_BIN env vars -> ./.venv/bin and ./.tools (lab layout) -> PATH
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent  # the iacgen/ project root

# Severities we treat as build-failing. Checkov emits these strings; Trivy emits
# the same set in its config results.
BLOCKING_SEVERITIES = {"HIGH", "CRITICAL"}


@dataclass
class Finding:
    """One normalized security finding from any scanner."""

    scanner: str          # "checkov" | "trivy"
    rule_id: str          # e.g. "CKV_AWS_20" or "AVD-AWS-0089"
    title: str            # short human-readable message
    severity: str         # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN"
    file_path: str        # path relative to the scanned module
    start_line: int       # 1-based; 1 when the scanner gives no line


@dataclass
class ScanResult:
    """All findings for one module scan, plus a blocking summary."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.severity in BLOCKING_SEVERITIES]

    @property
    def has_blocking(self) -> bool:
        return len(self.blocking) > 0

    def counts_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts


def _resolve(tool: str, env_var: str, local_dirs: list[Path]) -> str:
    """Find a pinned binary: env override -> lab-local dir -> PATH."""
    override = os.environ.get(env_var)
    if override:
        return override
    for d in local_dirs:
        candidate = d / tool
        if candidate.exists():
            return str(candidate)
    found = shutil.which(tool)
    if found:
        return found
    raise FileNotFoundError(
        f"{tool} not found. Set {env_var}, or install the pinned binary into "
        f"one of {[str(d) for d in local_dirs]}, or put it on PATH."
    )


def checkov_bin() -> str:
    return _resolve("checkov", "CHECKOV_BIN", [_REPO / ".venv" / "bin"])


def trivy_bin() -> str:
    return _resolve("trivy", "TRIVY_BIN", [_REPO / ".tools"])


def conftest_bin() -> str:
    return _resolve("conftest", "CONFTEST_BIN", [_REPO / ".tools"])


def run_checkov(module_dir: str | Path) -> ScanResult:
    """Run Checkov over a Terraform directory and normalize its JSON findings.

    Checkov exits non-zero when checks fail, which is expected, so we do not
    raise on a non-zero return code; we parse the JSON either way.
    """
    module_dir = Path(module_dir)
    proc = subprocess.run(
        [checkov_bin(), "--directory", str(module_dir),
         "--output", "json", "--compact", "--quiet"],
        capture_output=True, text=True, check=False,
    )
    stdout = proc.stdout.strip()
    if not stdout:
        return ScanResult()
    data = json.loads(stdout)
    # Checkov returns a dict for one framework or a list when several run.
    blocks = data if isinstance(data, list) else [data]

    findings: list[Finding] = []
    for block in blocks:
        results = block.get("results", {})
        for failed in results.get("failed_checks", []):
            sev = (failed.get("severity") or "UNKNOWN")
            sev = sev.upper() if isinstance(sev, str) else "UNKNOWN"
            line_range = failed.get("file_line_range") or [1]
            findings.append(Finding(
                scanner="checkov",
                rule_id=failed.get("check_id", "UNKNOWN"),
                title=failed.get("check_name", ""),
                severity=sev,
                file_path=_rel(failed.get("file_path", ""), module_dir),
                start_line=int(line_range[0]) if line_range else 1,
            ))
    return ScanResult(findings=findings)


def run_trivy(module_dir: str | Path) -> ScanResult:
    """Run `trivy config` over a Terraform directory and normalize its JSON.

    `--skip-check-update` makes the scan offline and deterministic: Trivy uses
    the misconfig checks bundle already in its cache instead of pulling the
    latest from ghcr.io on every run. CI pre-fetches the bundle once (see the
    ch14-iacgen job), then every scan runs with this flag so the loop never
    blocks on a network call. Remove the flag and Trivy hangs in an air-gapped
    runner.
    """
    module_dir = Path(module_dir)
    proc = subprocess.run(
        [trivy_bin(), "config", str(module_dir),
         "--format", "json", "--quiet", "--skip-check-update"],
        capture_output=True, text=True, check=False,
    )
    stdout = proc.stdout.strip()
    if not stdout:
        return ScanResult()
    data = json.loads(stdout)

    findings: list[Finding] = []
    for result in data.get("Results", []):
        target = result.get("Target", "")
        for mis in result.get("Misconfigurations", []):
            sev = (mis.get("Severity") or "UNKNOWN").upper()
            cause = mis.get("CauseMetadata") or {}
            start = (cause.get("StartLine") or 1)
            findings.append(Finding(
                scanner="trivy",
                rule_id=mis.get("ID", "UNKNOWN"),
                title=mis.get("Title", mis.get("Message", "")),
                severity=sev,
                file_path=_rel(target, module_dir),
                start_line=int(start) if start else 1,
            ))
    return ScanResult(findings=findings)


def scan_parallel(module_dir: str | Path) -> ScanResult:
    """Run Checkov AND Trivy concurrently and merge their findings.

    Scanners are independent processes with no shared state, so they run in a
    thread pool: the wall-clock cost of a scan pass is max(checkov, trivy), not
    their sum. The merged ScanResult is what the loop and the gate consume.
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        checkov_future = pool.submit(run_checkov, module_dir)
        trivy_future = pool.submit(run_trivy, module_dir)
        checkov_result = checkov_future.result()
        trivy_result = trivy_future.result()
    return ScanResult(findings=checkov_result.findings + trivy_result.findings)


def _rel(path: str, module_dir: Path) -> str:
    """Best-effort module-relative path for stable SARIF locations."""
    if not path:
        return "main.tf"
    p = Path(path)
    # Checkov reports paths like "/main.tf" (relative to the scan root).
    name = p.name if p.is_absolute() else str(p)
    return name
