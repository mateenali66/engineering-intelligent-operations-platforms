"""The STUBBED LLM: generate() and repair() return recorded Terraform fixtures.

This is the honest CI-vs-LLM split. A real iacgen would call a model here:

    generate(prompt) -> model writes Terraform for `prompt`
    repair(module, findings) -> model rewrites `module` to fix `findings`

In CI there is no LLM API key and no network egress, so both functions return
RECORDED fixtures from fixtures/ instead. The fixtures were captured to be
realistic: rev1 is the kind of insecure module a careless prompt produces, rev2
is the hardened rewrite a repair prompt produces. Everything downstream (the
parallel scanners, the bounded loop, the OPA gate, the SARIF) runs for REAL
against these recorded modules.

The `production_generate` / `production_repair` docstrings show the live shapes
the chapter swaps in; they are validation-only and never called in CI.
"""

from __future__ import annotations

import shutil
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
FIXTURES = _REPO / "fixtures"

# The ordered revision sequence the recorded loop walks: insecure -> hardened.
# generate() returns the first; each repair() returns the next.
BOUNDED_SEQUENCE = ["rev1_insecure", "rev2_hardened"]

# The degradation sequence for Lab 3 (the refinement-degradation paradox). It is
# a DETERMINISTIC ILLUSTRATION, not a live LLM run: each "repair" trades one
# finding for another so an UNCAPPED loop never converges. See generate.py's
# degradation_* helpers and labs/lab3_degradation.py.
DEGRADATION_SEQUENCE = [
    "rev1_insecure",
    "degrade_a_policy_wildcard",
    "degrade_b_back_to_acl",
]

# rev1 carries the same plan.json (no SSE) the bounded loop uses. The degrade_*
# fixtures do not ship a plan.json because Lab 3 never reaches the gate: the
# point is that the uncapped loop never converges, so the gate is never run.


def _materialize(fixture_name: str, workdir: str | Path) -> Path:
    """Copy a recorded fixture module into a fresh working directory."""
    src = FIXTURES / fixture_name
    if not src.is_dir():
        raise FileNotFoundError(f"recorded fixture {fixture_name} not found at {src}")
    dest = Path(workdir)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


def generate(prompt: str, workdir: str | Path,
             sequence: list[str] | None = None) -> Path:
    """STUBBED LLM generate. Returns the first recorded revision for `prompt`.

    In CI this ignores the prompt text and returns the recorded rev1 module, so
    the lab is deterministic and key-free. `prompt` is kept in the signature
    because the chapter's narration ("a secure S3 bucket Terraform module") is
    the request a real model would answer.
    """
    seq = sequence or BOUNDED_SEQUENCE
    return _materialize(seq[0], workdir)


def repair(workdir: str | Path, findings, iteration: int,
           sequence: list[str] | None = None) -> Path:
    """STUBBED LLM repair. Returns the NEXT recorded revision in the sequence.

    A real repair() would feed `findings` to a model and get a rewritten module
    back. Here `iteration` (1-based: the number of repairs already done) indexes
    into the recorded revision sequence. `findings` is accepted and ignored so
    the signature matches the live shape the chapter swaps in.
    """
    seq = sequence or BOUNDED_SEQUENCE
    idx = min(iteration, len(seq) - 1)  # clamp at the last recorded revision
    return _materialize(seq[idx], workdir)


def production_generate(prompt: str):  # pragma: no cover - validation-only
    """Live generate (NOT run in CI): needs an LLM API key and network egress.

        client = OpenAI()  # or Anthropic, Bedrock, a local server, etc.
        resp = client.responses.create(
            model="gpt-4o",
            instructions=(
                "You are an IaC generator. Output ONLY valid Terraform HCL, no "
                "prose. Target AWS provider 6.x and Terraform 1.9+."
            ),
            input=prompt,
        )
        return resp.output_text  # untrusted: it still goes through the scanners
    """
    raise NotImplementedError(
        "production_generate needs an LLM API key and network egress; CI uses "
        "the recorded fixture via generate()."
    )


def production_repair(module_src: str, findings):  # pragma: no cover - validation-only
    """Live repair (NOT run in CI): feeds findings back to the model.

        prompt = (
            "Here are the Checkov and Trivy findings for the Terraform you "
            "wrote. Fix every HIGH/CRITICAL finding and return ONLY the "
            f"corrected module.\\n\\nMODULE:\\n{module_src}\\n\\nFINDINGS:\\n"
            + "\\n".join(f"{f.scanner} {f.rule_id} ({f.severity}): {f.title}"
                         for f in findings)
        )
        resp = client.responses.create(model="gpt-4o", input=prompt)
        return resp.output_text  # still untrusted: re-scan before apply
    """
    raise NotImplementedError(
        "production_repair needs an LLM API key and network egress; CI uses the "
        "recorded revision sequence via repair()."
    )
