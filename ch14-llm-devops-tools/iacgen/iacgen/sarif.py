"""SARIF 2.1.0 emission for iacgen findings.

Two honest paths, both shown in the chapter:

  1. NATIVE: Checkov and Trivy each emit valid SARIF 2.1.0 on their own
     (`checkov --output sarif`, `trivy config --format sarif`). In production you
     would hand those native files straight to GitHub code scanning and never
     write SARIF by hand. `native_checkov_sarif` and `native_trivy_sarif` run the
     pinned binaries and return their SARIF so the chapter can show it works.

  2. HAND-ROLLED: when you have already normalized findings from several scanners
     into one stream (as iacgen's loop does), it is cleaner to emit one merged
     SARIF report than to post N native files. `to_sarif` builds a minimal but
     schema-valid SARIF 2.1.0 log from a list of Finding records.

`validate_sarif` checks the structural invariants GitHub's ingestion relies on,
so the smoke test and CI can assert the output is well-formed without a network
call to a schema service.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .scanners import Finding, checkov_bin, trivy_bin

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/"
    "schema/sarif-schema-2.1.0.json"
)

# SARIF result.level is one of error|warning|note|none. Map IaC severities onto
# it so every blocking finding (HIGH, CRITICAL, or unranked) surfaces as an
# error in GitHub code scanning, matching what the loop blocks on.
_LEVEL_BY_SEVERITY = {
    "CRITICAL": "error",
    "HIGH": "error",
    "MEDIUM": "warning",
    "LOW": "note",
    "UNKNOWN": "error",
}


def to_sarif(findings: list[Finding], tool_name: str = "iacgen") -> dict:
    """Build a minimal, schema-valid SARIF 2.1.0 log from merged findings.

    One run, one tool driver, one rule per distinct rule_id, one result per
    finding. This is the merged report iacgen emits after its scan-repair loop.
    """
    rules: dict[str, dict] = {}
    results: list[dict] = []

    for f in findings:
        if f.rule_id not in rules:
            rules[f.rule_id] = {
                "id": f.rule_id,
                "name": f.rule_id,
                "shortDescription": {"text": f.title or f.rule_id},
                "properties": {
                    "security-severity": _security_severity(f.severity),
                    "scanner": f.scanner,
                },
            }
        results.append({
            "ruleId": f.rule_id,
            "level": _LEVEL_BY_SEVERITY.get(f.severity, "warning"),
            "message": {"text": f"[{f.scanner}] {f.title}".strip()},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": f.file_path or "main.tf"},
                    "region": {"startLine": max(1, f.start_line)},
                }
            }],
            "properties": {"severity": f.severity},
        })

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [{
            "tool": {
                "driver": {
                    "name": tool_name,
                    "informationUri": "https://github.com/Apress/iacgen",
                    "version": "0.1.0",
                    "rules": list(rules.values()),
                }
            },
            "results": results,
        }],
    }


def _security_severity(severity: str) -> str:
    """GitHub reads properties.security-severity as a 0.0-10.0 CVSS-like score."""
    return {
        "CRITICAL": "9.5",
        "HIGH": "8.0",
        "MEDIUM": "5.0",
        "LOW": "2.0",
        "UNKNOWN": "5.0",
    }.get(severity, "5.0")


def validate_sarif(doc: dict) -> None:
    """Assert the structural invariants GitHub code scanning ingestion needs.

    Raises AssertionError on the first violation. This is a lightweight,
    offline structural check, not a full JSON-schema validation, but it covers
    the fields GitHub rejects an upload over: version, runs[], each run's
    tool.driver.name, and each result's ruleId/level/message/locations.
    """
    assert doc.get("version") == SARIF_VERSION, "version must be 2.1.0"
    assert isinstance(doc.get("runs"), list) and doc["runs"], "runs[] must be non-empty"
    for run in doc["runs"]:
        driver = run.get("tool", {}).get("driver", {})
        assert driver.get("name"), "each run needs tool.driver.name"
        assert isinstance(run.get("results"), list), "each run needs a results[]"
        for res in run["results"]:
            assert res.get("ruleId"), "result missing ruleId"
            assert res.get("level") in {"error", "warning", "note", "none"}, \
                f"result has invalid level {res.get('level')!r}"
            assert res.get("message", {}).get("text"), "result missing message.text"
            locs = res.get("locations")
            assert isinstance(locs, list) and locs, "result missing locations[]"
            region = locs[0]["physicalLocation"]["region"]
            assert region["startLine"] >= 1, "startLine must be >= 1"
    # Round-trips as JSON (no non-serializable values leaked in).
    json.dumps(doc)


def write_sarif(doc: dict, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(json.dumps(doc, indent=2))
    return path


def native_checkov_sarif(module_dir: str | Path) -> dict:
    """Run `checkov --output sarif` and return its native SARIF 2.1.0 log.

    Production path: no hand-rolling. Checkov writes a `results_sarif.sarif`
    file (not stdout) under --output-file-path that you can hand straight to
    GitHub code scanning. We read it back here so the lab can show it is valid.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as out:
        subprocess.run(
            [checkov_bin(), "--directory", str(module_dir),
             "--output", "sarif", "--output-file-path", out, "--quiet"],
            capture_output=True, text=True, check=False,
        )
        sarif_file = Path(out) / "results_sarif.sarif"
        return json.loads(sarif_file.read_text())


def native_trivy_sarif(module_dir: str | Path) -> dict:
    """Run `trivy config --format sarif` and return its native SARIF 2.1.0 log."""
    proc = subprocess.run(
        [trivy_bin(), "config", str(module_dir),
         "--format", "sarif", "--quiet", "--skip-check-update"],
        capture_output=True, text=True, check=False,
    )
    return json.loads(proc.stdout)
