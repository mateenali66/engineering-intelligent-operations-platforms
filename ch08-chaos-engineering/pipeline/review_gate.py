"""Listing 8-3: a human-review gate for an LLM-drafted chaos experiment.

An LLM can draft a Chaos Mesh experiment from a plain-English request, the same
way Chapter 4 let one draft Terraform. And the same rule applies: generate, then
check, then a human approves before anything runs. This gate enforces the blast
radius an LLM might quietly widen. It does not call an LLM; it validates the
manifest an LLM proposed, and returns the reasons a human needs to decide.

A review gate is an allowlist problem: block anything not explicitly recognized
as bounded. So an absent bound is a finding, not a pass. A missing duration lets
the fault run until someone deletes it, and a wide `fixed` or percent mode is the
same blast-radius widening as `mode: all` wearing a number.
"""

from __future__ import annotations

ALLOWED_NAMESPACES = {"default", "staging"}
MAX_DURATION_SECONDS = 120
MAX_FIXED_PODS = 3
MAX_PERCENT = 25
WIDE_MODES = {"fixed", "fixed-percent", "random-max-percent"}


def _duration_seconds(value):
    """Parse a Go-style duration like '30s' or '2m' into seconds."""
    value = str(value).strip()
    if value.endswith("ms"):
        return float(value[:-2]) / 1000
    if value.endswith("s"):
        return float(value[:-1])
    if value.endswith("m"):
        return float(value[:-1]) * 60
    return float(value)


def review_experiment(manifest):
    """Return {"auto_blocked", "findings"} for a proposed Chaos Mesh manifest."""
    spec = manifest.get("spec", {})
    findings = []

    mode = spec.get("mode")
    if mode == "all":
        findings.append("blast radius: mode 'all' hits every matched pod; "
                        "prefer 'one' or a fixed count")
    elif mode in WIDE_MODES:
        cap = MAX_PERCENT if mode.endswith("percent") else MAX_FIXED_PODS
        unit = "percent" if mode.endswith("percent") else "pods"
        value = spec.get("value")
        if value is None or float(value) > cap:
            findings.append(f"blast radius: mode '{mode}' value {value!r} "
                            f"exceeds the {cap}-{unit} cap; prefer 'one'")

    namespaces = set(spec.get("selector", {}).get("namespaces", []))
    if not namespaces <= ALLOWED_NAMESPACES:
        findings.append(f"namespace: {namespaces - ALLOWED_NAMESPACES} not in "
                        f"the allowlist {sorted(ALLOWED_NAMESPACES)}")

    duration = spec.get("duration")
    if duration is None:
        findings.append("duration: none set; the fault runs until deleted, "
                        "the longest blast radius there is")
    elif _duration_seconds(duration) > MAX_DURATION_SECONDS:
        findings.append(f"duration {duration} exceeds the "
                        f"{MAX_DURATION_SECONDS}s cap")

    # The gate never auto-approves; a clean check still routes to a human.
    return {"auto_blocked": bool(findings), "findings": findings}


if __name__ == "__main__":
    safe = {"spec": {"mode": "one", "duration": "30s",
                     "selector": {"namespaces": ["default"]}}}
    risky = {"spec": {"mode": "all", "duration": "10m",
                      "selector": {"namespaces": ["kube-system"]}}}
    print("safe:", review_experiment(safe))
    print("risky:", review_experiment(risky))
