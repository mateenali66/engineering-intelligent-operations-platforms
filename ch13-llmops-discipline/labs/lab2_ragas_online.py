"""Listing 13-2b (validation-only): the Ragas equivalent of the eval gate.

Ragas is the other half of the eval-gate story the chapter names: DeepEval gives
us the offline exact-match gate that CI runs (lab2_eval_gate.py), and Ragas gives
the RAG-specific metrics (faithfulness, answer correctness, context precision)
you reach for once a real retriever and a judge model are in play.

Why this file is validation-only and NOT run in CI:

  1. The RAG metrics that matter (Faithfulness, AnswerCorrectness,
     ContextPrecision) are LLM-as-judge: they need an LLM API key and network
     egress, which CI does not have. That alone matches the honesty split used
     for Chapter 11's vLLM path and Chapter 12's Phoenix path.

  2. Even Ragas's non-LLM metrics (ExactMatch, RougeScore, BleuScore) could not
     be imported offline in the verified mid-2026 environment: ragas==0.4.3
     pulls `langchain_community.chat_models.vertexai` at import time, and the
     langchain-community 0.4.x line sunset that module, so `import ragas` raises
     ModuleNotFoundError before any metric is reachable. Pinning an older
     langchain-community only cascades into a langchain-core/langchain-openai
     mismatch. So the deterministic offline gate the chapter ships is the
     DeepEval one; Ragas is the production/online metric.

This file is compile-checked by CI (py_compile), not executed, exactly like
Chapter 12's lab4_phoenix_genai_eval.py.

Run it locally, after `pip install ragas==0.4.3` in an environment where the
langchain integration resolves, with an LLM judge configured:

    export OPENAI_API_KEY=...
    python lab2_ragas_online.py
"""

from __future__ import annotations

# --- illustrative only: not imported or executed by CI -----------------------


def ragas_rag_gate():  # pragma: no cover - validation-only
    """Score a RAG answer with Ragas faithfulness, then gate on the threshold.

    Faithfulness measures whether the answer is grounded in the retrieved
    context (no hallucination), scored 0..1 by an LLM judge. The gate is the same
    pattern as the DeepEval one: if the score drops below the threshold, fail the
    build.
    """
    from ragas import SingleTurnSample
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness

    # The judge model. This is the call that needs an API key and egress.
    from langchain_openai import ChatOpenAI

    judge = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o"))
    faithfulness = Faithfulness(llm=judge)

    sample = SingleTurnSample(
        user_input="Which deployment should I restart for the checkout latency spike?",
        response="Restart the checkout deployment after the 14:02 rollout.",
        retrieved_contexts=[
            "Runbook: checkout p95 latency spikes after a bad rollout are fixed "
            "by restarting the checkout deployment.",
        ],
    )

    import asyncio

    score = asyncio.run(faithfulness.single_turn_ascore(sample))

    threshold = 0.7
    assert score >= threshold, (
        f"Ragas faithfulness {score:.2f} below gate threshold {threshold}"
    )
    return score


if __name__ == "__main__":
    print(
        "Listing 13-2b is validation-only: Ragas RAG metrics need an LLM judge "
        "(API key + egress), and ragas==0.4.3 cannot even be imported offline in "
        "the verified mid-2026 environment. CI runs the DeepEval exact-match gate "
        "in lab2_eval_gate.py instead. See the module docstring."
    )
