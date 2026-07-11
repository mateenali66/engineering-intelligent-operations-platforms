"""Listing 13-2 (RUNS IN CI): a CI eval gate that fails on metric regression.

The teaching point is the GATING PATTERN, not the judge quality: a Pytest test
that fails the build when an eval metric drops below a threshold, so a prompt or
model change that regresses answer quality cannot merge silently.

To run this headless with no API key we use DeepEval's ExactMatchMetric, a
NON-LLM, deterministic, offline metric: it is a plain string-equality check
between actual_output and expected_output, no model and no token cost. The
gating mechanics (LLMTestCase, a metric with a threshold, assert_test failing
the build) are identical whether the metric behind them is a deterministic
string check or a live LLM-as-judge such as G-Eval or Answer Relevancy. The
chapter swaps the metric, not the gate.

The two named cases below are what the gate looks like in practice:

  test_good_release  : the model's answer matches the golden answer -> PASS.
  test_regressed_release : a regressed prompt produced the wrong answer ->
                           the metric scores 0, below threshold, and assert_test
                           FAILS the build. We assert that failure with
                           pytest.raises so the listing is self-checking: if the
                           gate ever stopped failing on a regression, this test
                           would itself fail.

The production metric (LLM-as-judge: G-Eval, Answer Relevancy, Faithfulness, or
the Ragas faithfulness/answer-correctness metrics) needs an LLM API key and
network egress, so it is validation-only here. See
`production_llm_judge_metric` for the shape, and lab2_ragas_online.py for the
Ragas equivalent.

Run the gate:
    deepeval test run lab2_eval_gate.py          # DeepEval's pytest wrapper
    # or plain pytest, which also works because the cases use assert_test:
    pytest lab2_eval_gate.py
"""

from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.metrics import ExactMatchMetric
from deepeval.test_case import LLMTestCase

# The golden answer the RAG chatbot is expected to produce for a known runbook
# question. In a real eval set this is one row of many; the gate runs over the
# whole set.
QUESTION = "Which deployment should I restart when checkout p95 latency tripled?"
GOLDEN_ANSWER = "Restart the checkout deployment."


def good_release_output() -> str:
    """Stands in for the RAG pipeline on a healthy prompt/model: correct answer."""
    return "Restart the checkout deployment."


def regressed_release_output() -> str:
    """Stands in for the RAG pipeline after a regression: wrong deployment."""
    return "Restart the payments deployment."


def test_good_release():
    """The gate PASSES: the answer exactly matches the golden answer."""
    test_case = LLMTestCase(
        input=QUESTION,
        actual_output=good_release_output(),
        expected_output=GOLDEN_ANSWER,
    )
    # threshold 1.0: exact-match must be perfect. assert_test raises (fails the
    # build) if the metric scores below threshold; here it scores 1.0 and passes.
    assert_test(test_case, [ExactMatchMetric(threshold=1.0)])


def test_regressed_release():
    """The gate FAILS on a regression, and we assert that it fails.

    assert_test raises AssertionError when the metric is below threshold. Wrapping
    it in pytest.raises makes this listing self-checking: it demonstrates, in CI,
    that a regressed answer actually trips the gate. Remove the pytest.raises and
    this becomes the real failing gate you would see on a bad pull request.
    """
    test_case = LLMTestCase(
        input=QUESTION,
        actual_output=regressed_release_output(),
        expected_output=GOLDEN_ANSWER,
    )
    with pytest.raises(AssertionError):
        assert_test(test_case, [ExactMatchMetric(threshold=1.0)])


def production_llm_judge_metric():  # pragma: no cover - validation-only
    """Production metric (NOT run in CI): an LLM-as-judge gate.

    Same gate, richer metric. G-Eval scores the answer against a rubric using an
    LLM judge, so it catches paraphrases and partially-correct answers that an
    exact-match check would reject. It needs an LLM API key (OPENAI_API_KEY or a
    custom DeepEvalBaseLLM model) and network egress, so CI cannot run it.

        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCaseParams

        relevancy = GEval(
            name="Runbook correctness",
            criteria=(
                "Does actual_output name the same remediation as "
                "expected_output, even if worded differently?"
            ),
            evaluation_params=[
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
            threshold=0.7,
            model="gpt-4o",        # the judge; needs OPENAI_API_KEY
        )
        assert_test(test_case, [relevancy])

    To run fully offline with an LLM judge you would subclass DeepEvalBaseLLM
    around a local model (Ollama, etc.); that still needs the model weights and a
    running server, which CI does not have, so it stays validation-only.
    """
    raise NotImplementedError(
        "production_llm_judge_metric is validation-only: G-Eval needs an LLM "
        "API key and network egress. CI uses the offline ExactMatchMetric gate."
    )


if __name__ == "__main__":
    # Allow running as a plain script too (outside pytest) to show both outcomes.
    good = LLMTestCase(
        input=QUESTION,
        actual_output=good_release_output(),
        expected_output=GOLDEN_ANSWER,
    )
    metric = ExactMatchMetric(threshold=1.0)
    metric.measure(good)
    print(f"good release   : score={metric.score} (>= 1.0 -> gate PASSES)")

    bad = LLMTestCase(
        input=QUESTION,
        actual_output=regressed_release_output(),
        expected_output=GOLDEN_ANSWER,
    )
    metric_bad = ExactMatchMetric(threshold=1.0)
    metric_bad.measure(bad)
    print(f"regressed release: score={metric_bad.score} (< 1.0 -> gate FAILS)")
