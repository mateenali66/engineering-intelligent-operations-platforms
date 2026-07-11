"""Tests for the unified trace: infra and gen_ai spans share one trace, the
gen_ai span carries the current GenAI attribute names, and cost is computed."""

from __future__ import annotations

from aiosp.cost import APP_GENAI_COST_USD, compute_cost
from aiosp.tracing import (
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    capture,
)


def test_infra_and_genai_share_one_trace():
    spans = capture()
    assert len(spans) == 2
    assert len({s.context.trace_id for s in spans}) == 1


def test_gen_ai_span_uses_current_attribute_names():
    spans = capture()
    gen = next(
        s for s in spans if any(k.startswith("gen_ai.") for k in (s.attributes or {}))
    )
    attrs = dict(gen.attributes)
    # Current names, not the deprecated gen_ai.system / prompt_tokens.
    assert attrs[GEN_AI_PROVIDER_NAME] == "aiosp.kserve"
    assert attrs[GEN_AI_REQUEST_MODEL] == "incident-copilot"
    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 220
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 38
    assert "gen_ai.system" not in attrs


def test_cost_is_on_the_gen_ai_span_and_matches_the_helper():
    spans = capture()
    gen = next(
        s for s in spans if any(k.startswith("gen_ai.") for k in (s.attributes or {}))
    )
    attrs = dict(gen.attributes)
    expected = compute_cost("incident-copilot", 220, 38)
    assert attrs[APP_GENAI_COST_USD] == expected
    assert expected > 0


def test_cost_helper_is_deterministic():
    assert compute_cost("incident-copilot", 1000, 1000) == 0.002
    assert compute_cost("incident-copilot", 0, 0) == 0.0
