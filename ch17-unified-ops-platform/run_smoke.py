"""Smoke test for the AIOSP capstone: prove the platform is one substrate and
the trace is one trace, with no cluster, no LLM, no GPU.

Runs the two CI-runnable pieces and asserts their key outcomes:
  1. The convergence check passes: three disciplines share the serving API, the
     Argo delivery loop, and the OTLP observability endpoint.
  2. The unified trace carries an infra span and a gen_ai child span in ONE
     trace, with token counts and a computed cost on the gen_ai span.

The kind bring-up (setup.sh) and the live KServe/Argo CD/Backstage deploy are NOT
run here: they need a real cluster and, for the LLM, a GPU. The manifests they
apply are yaml-linted and structurally checked in CI; the live apply is local.
"""

from __future__ import annotations

from aiosp.convergence import check
from aiosp.cost import APP_GENAI_COST_USD
from aiosp.tracing import (
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    capture,
)


def main() -> None:
    # 1. Convergence: substrates are shared.
    report = check()
    assert report["serving"] == (
        "serving.kserve.io/v1beta1",
        "InferenceService",
    )
    formats = {fmt for _, _, fmt in report["rows"]}
    assert {"sklearn", "huggingface"} <= formats
    assert len(report["rows"]) == 3
    print("convergence: PASS (serving, delivery, observability all shared)")

    # 2. Unified trace: infra + gen_ai in one trace, with tokens and cost.
    spans = capture()
    assert len(spans) == 2, f"expected 2 spans, got {len(spans)}"
    assert len({s.context.trace_id for s in spans}) == 1
    gen = next(
        s for s in spans if any(k.startswith("gen_ai.") for k in (s.attributes or {}))
    )
    attrs = dict(gen.attributes)
    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 220
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 38
    assert attrs[APP_GENAI_COST_USD] > 0
    print(
        "unified trace: PASS (infra + gen_ai in one trace, "
        f"cost=${attrs[APP_GENAI_COST_USD]})"
    )

    print("smoke: ok")


if __name__ == "__main__":
    main()
