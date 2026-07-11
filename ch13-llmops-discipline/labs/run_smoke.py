"""End-to-end smoke test for Chapter 13 labs 1-3 (headless, no API key, no net).

Runs the three CI-runnable LLMOps labs and asserts the outcomes the chapter
teaches:

  Lab 1 (OTel GenAI span) : a stubbed chat call emits exactly one span whose name
                            is "{operation} {model}" and that carries the gen_ai.*
                            attributes the semantic conventions ask for (provider,
                            request/response model, operation, token usage).
  Lab 2 (eval gate)       : the DeepEval ExactMatchMetric gate scores 1.0 on the
                            good release (gate PASSES) and 0.0 on the regressed
                            release (a real gate would FAIL the build). Both are
                            asserted here.
  Lab 3 (cost meter)      : the same span token counts become dollars through an
                            explicit price table; per-route spend accumulates; and
                            the daily budget cap downshifts the expensive route and
                            refuses a request already on the cheapest route.

This is what CI runs. Prints "smoke: ok" when every assertion holds. No LLM API
key, no network, no collector, no GPU. The Langfuse OTLP export (Lab 1), the
Ragas online metric (lab2_ragas_online.py), and the live Promptfoo run
(redteam/promptfooconfig.yaml) are validation-only and are not exercised here.
"""

from __future__ import annotations

from deepeval.metrics import ExactMatchMetric
from deepeval.test_case import LLMTestCase

import lab1_genai_span
import lab2_eval_gate
import lab3_cost_meter


def main():
    # Lab 1: GenAI span emission and capture.
    captured = lab1_genai_span.run()
    attrs = captured["attributes"]
    print(f"lab1 span: name={captured['name']!r} "
          f"provider={attrs.get('gen_ai.provider.name')!r} "
          f"in_tok={attrs.get('gen_ai.usage.input_tokens')} "
          f"out_tok={attrs.get('gen_ai.usage.output_tokens')}")

    # The span name must follow the convention "{operation} {model}".
    assert captured["name"] == "chat anomaly-copilot-v1", \
        "span name should be '{gen_ai.operation.name} {gen_ai.request.model}'"
    # The gen_ai.* attributes the conventions ask for must be present.
    for key in (
        "gen_ai.operation.name",
        "gen_ai.provider.name",
        "gen_ai.request.model",
        "gen_ai.response.model",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
    ):
        assert key in attrs, f"span is missing required GenAI attribute {key}"
    assert attrs["gen_ai.operation.name"] == "chat"
    assert isinstance(attrs["gen_ai.usage.input_tokens"], int)
    assert isinstance(attrs["gen_ai.usage.output_tokens"], int)

    # Lab 2: the eval gate. Score the good and regressed releases directly so the
    # smoke test asserts both the PASS and the would-be FAIL without relying on
    # pytest. These call the same functions the pytest gate uses.
    good = LLMTestCase(
        input=lab2_eval_gate.QUESTION,
        actual_output=lab2_eval_gate.good_release_output(),
        expected_output=lab2_eval_gate.GOLDEN_ANSWER,
    )
    good_metric = ExactMatchMetric(threshold=1.0)
    good_metric.measure(good)

    regressed = LLMTestCase(
        input=lab2_eval_gate.QUESTION,
        actual_output=lab2_eval_gate.regressed_release_output(),
        expected_output=lab2_eval_gate.GOLDEN_ANSWER,
    )
    regressed_metric = ExactMatchMetric(threshold=1.0)
    regressed_metric.measure(regressed)

    print(f"lab2 gate: good_score={good_metric.score} "
          f"regressed_score={regressed_metric.score}")

    assert good_metric.score == 1.0, "the good release should pass the eval gate"
    assert good_metric.is_successful(), "good release should be a successful gate"
    assert regressed_metric.score == 0.0, \
        "the regressed release should score 0 and fail the eval gate"
    assert not regressed_metric.is_successful(), \
        "regressed release must NOT pass: a real gate fails the build here"

    # Lab 3: the cost meter. Feed one request the exact token counts Lab 1 put on
    # the span, so the cost is derived from the same numbers, then replay the
    # opener's runaway and assert the budget cap engages.
    span_in = attrs["gen_ai.usage.input_tokens"]
    span_out = attrs["gen_ai.usage.output_tokens"]
    span_cost = lab3_cost_meter.cost_usd(lab3_cost_meter.FRONTIER, span_in, span_out)
    print(f"lab3 cost: span {span_in}/{span_out} tokens -> ${span_cost:.6f} on "
          f"{lab3_cost_meter.FRONTIER}")

    meter = lab3_cost_meter.run()
    frontier_spend = meter.cost_by_route[lab3_cost_meter.FRONTIER]
    mini_spend = meter.cost_by_route[lab3_cost_meter.MINI]
    print(f"lab3 ledger: frontier=${frontier_spend:.4f} mini=${mini_spend:.4f} "
          f"total=${meter.spent:.4f}")

    # The meter must have spent past the $1.00 budget (the runaway crossed it),
    # downshifted onto the cheap route (non-zero mini spend), and it must refuse a
    # cheapest-route request once over budget.
    assert meter.spent > 1.00, "the runaway workload should cross the $1.00 budget"
    assert mini_spend > 0.0, "over budget, the expensive route must downshift to mini"
    over = lab3_cost_meter.CostMeter(daily_budget_usd=0.0)
    try:
        over.route_for(lab3_cost_meter.MINI)
        raise AssertionError("a cheapest-route request over budget must be refused")
    except lab3_cost_meter.BudgetExceeded:
        pass

    print("smoke: ok")


if __name__ == "__main__":
    main()
