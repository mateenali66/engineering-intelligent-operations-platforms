"""Lab 1: the unified trace. Emit one trace that carries an infra span and a
gen_ai child span, then print it so token and cost sit beside the infra work.

The implementation is aiosp.tracing (Listing 17-1). This lab runs it and prints
the captured trace, which is what the chapter shows.

Run:
    export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
    python lab1_unified_trace.py
"""

from __future__ import annotations

from aiosp.tracing import (
    APP_GENAI_COST_USD,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    capture,
)


def main() -> None:
    spans = capture()
    trace_ids = {s.context.trace_id for s in spans}
    assert len(spans) == 2, f"expected 2 spans, got {len(spans)}"
    assert len(trace_ids) == 1, "infra and gen_ai spans must share one trace"
    print(f"one trace, {len(spans)} spans (infra + gen_ai):")
    for s in spans:
        attrs = dict(s.attributes or {})
        if any(k.startswith("gen_ai.") for k in attrs):
            print(
                f"  [gen_ai] {s.name}  "
                f"tokens(in/out)={attrs[GEN_AI_USAGE_INPUT_TOKENS]}/"
                f"{attrs[GEN_AI_USAGE_OUTPUT_TOKENS]}  "
                f"cost=${attrs[APP_GENAI_COST_USD]}"
            )
        else:
            print(f"  [infra]  {s.name}")


if __name__ == "__main__":
    main()
