"""Deterministic retrieval and answer metrics.

These run in CI with no LLM judge. The retrieval metrics (hit_rate,
precision_at_k) score a ranked id list against a labeled gold set. The eval-gate
metrics (context_precision, faithfulness_proxy) are deterministic stand-ins for
the LLM-judged Ragas metrics: they exercise the same gate mechanics (threshold,
pass/fail) without needing a key. The production gate uses the LLM-judged
faithfulness in eval_ragas.py; this is the "swap the metric, not the gate" pattern.
"""

from __future__ import annotations

import re


def hit_rate(ranked_ids: list[int], gold_ids: set[int], k: int) -> float:
    """1.0 if any gold id appears in the top k, else 0.0."""
    return 1.0 if set(ranked_ids[:k]) & gold_ids else 0.0


def precision_at_k(ranked_ids: list[int], gold_ids: set[int], k: int) -> float:
    """Fraction of the top k that are gold."""
    if k == 0:
        return 0.0
    topk = ranked_ids[:k]
    return sum(1 for i in topk if i in gold_ids) / k


def reciprocal_rank(ranked_ids: list[int], gold_ids: set[int]) -> float:
    """1/rank of the first gold id in the ranked list, else 0.0 (the term in MRR)."""
    for i, rid in enumerate(ranked_ids, start=1):
        if rid in gold_ids:
            return 1.0 / i
    return 0.0


def mean_metric(per_query: list[float]) -> float:
    """Mean of a per-query metric list."""
    return sum(per_query) / len(per_query) if per_query else 0.0


def context_precision(retrieved_ids: list[int], gold_ids: set[int], k: int) -> float:
    """Reference-based context precision: of the top k retrieved contexts, the
    fraction that are relevant. The non-LLM analogue of Ragas context precision.
    """
    return precision_at_k(retrieved_ids, gold_ids, k)


_WORD = re.compile(r"[a-z0-9][a-z0-9_-]*")
_STOP = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "are",
    "with", "see", "runbook", "restart", "deployment", "cluster",
}


def faithfulness_proxy(answer: str, contexts: list[str]) -> float:
    """Deterministic grounding proxy: the fraction of the answer's content tokens
    that appear in the retrieved contexts. NOT the LLM-judged Ragas faithfulness;
    a token-grounding stand-in that exercises the same gate, no key required.
    """
    ctx_tokens = set()
    for c in contexts:
        ctx_tokens.update(_WORD.findall(c.lower()))
    ans_tokens = [t for t in _WORD.findall(answer.lower()) if t not in _STOP]
    if not ans_tokens:
        return 0.0
    grounded = sum(1 for t in ans_tokens if t in ctx_tokens)
    return grounded / len(ans_tokens)
