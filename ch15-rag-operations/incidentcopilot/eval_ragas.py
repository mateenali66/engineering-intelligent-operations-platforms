"""VALIDATION-ONLY: the production RAG-evaluation wiring.

This file is py_compile-checked in CI but NEVER imported or executed there, for
two reasons: the metrics call an LLM judge (no key in CI), and ragas itself
cannot be imported in a current environment. Verified June 2026: `import ragas`
(0.4.3) fails with
    ModuleNotFoundError: No module named 'langchain_community.chat_models.vertexai'
because ragas/llms/base.py imports ChatVertexAI at module load and
langchain-community 0.4.2 removed that submodule; no pin coexists with the
langchain 1.x line the chapter uses. The CI gate therefore runs the deterministic
metrics in evaluate.py instead (swap the metric, not the gate). trulens-core
DOES import cleanly, so its triad wiring is the import-checked path.
"""

from __future__ import annotations


def ragas_faithfulness_gate(samples, threshold: float = 0.8):  # pragma: no cover
    """Shape only: the production LLM-judged faithfulness + context-precision gate.

        from ragas import EvaluationDataset, evaluate
        from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference
        from ragas.llms import LangchainLLMWrapper
        from langchain_openai import ChatOpenAI

        judge = LangchainLLMWrapper(ChatOpenAI(model="gpt-4.1-mini"))
        dataset = EvaluationDataset.from_list(samples)
        result = evaluate(
            dataset,
            metrics=[Faithfulness(llm=judge), LLMContextPrecisionWithReference(llm=judge)],
        )
        return result["faithfulness"] >= threshold

    Faithfulness decomposes the answer into claims and checks each against the
    retrieved context with the judge, so it needs a key. Not run in CI.
    """
    raise NotImplementedError("ragas gate is validation-only; see docstring and README")


def trulens_rag_triad():  # pragma: no cover - validation-only
    """Shape only: the TruLens RAG triad (context relevance, groundedness,
    answer relevance). trulens-core imports cleanly, but the feedback providers
    call an LLM judge, so the triad is validation-only.

        from trulens.core import TruSession, Feedback
        session = TruSession()
        # feedback functions wrap an LLM provider (groundedness / relevance);
        # they need a key, so they are not executed in CI.
    """
    raise NotImplementedError("trulens triad is validation-only; see docstring")
