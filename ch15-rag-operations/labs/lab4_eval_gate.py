"""Listing 15-4: wire RAG evaluation into CI as a gate. The gate fails the build
when faithfulness or context precision regresses. In CI it runs DETERMINISTIC
metrics (a token-grounding faithfulness proxy and reference-based context
precision), so the gate mechanics run with no LLM judge and no key. The
production gate uses the LLM-judged Ragas faithfulness in eval_ragas.py: swap the
metric, not the gate. Runs in CI.
"""

from __future__ import annotations

from incidentcopilot.evaluate import context_precision, faithfulness_proxy

# The retrieved context for a checkout incident query (the real runbook chunk).
RETRIEVED_CONTEXTS = [
    "A checkout pod in CrashLoopBackOff has failed its startup repeatedly and "
    "Kubernetes is backing off restarts. Describe the pod and read the last "
    "terminated state: an exit code 137 means the container was OOM-killed, while "
    "a non-zero application exit usually points at a failed migration or a missing "
    "secret. Check the readiness and liveness probe timing before assuming the "
    "application is at fault, because an aggressive liveness probe can kill a slow "
    "starter and produce the same CrashLoopBackOff symptom.",
]
RETRIEVED_IDS = [8, 1, 14]    # ranked chunk ids from hybrid_search for the query
GOLD_IDS = {8}                # the CrashLoopBackOff triage chunk

# A grounded answer: every claim traces to the retrieved context above.
GOOD_ANSWER = "Read the last terminated state: exit code 137 means the container was OOM-killed, and an aggressive liveness probe can kill a slow starter."
# A hallucinated answer: names a service, region, and count that appear in no context.
HALLUCINATED_ANSWER = "Restart the payments-v2 service in the frankfurt region and scale to fifty replicas."
# The proxy's blind spot: the runbook's own words with the instruction reversed.
# It is NOT supported by the context, yet it clears the overlap threshold.
REVERSED_ANSWER = "Assume the application is at fault before you check the readiness and liveness probe timing."

THRESHOLD = 0.8


def gate(answer: str) -> bool:
    """Pass only if the overlap proxy and context precision clear threshold."""
    faith = faithfulness_proxy(answer, RETRIEVED_CONTEXTS)
    ctx_p = context_precision(RETRIEVED_IDS, GOLD_IDS, k=3)
    return faith >= THRESHOLD and ctx_p >= 0.30


def main() -> None:
    cp = context_precision(RETRIEVED_IDS, GOLD_IDS, k=3)
    fg = faithfulness_proxy(GOOD_ANSWER, RETRIEVED_CONTEXTS)
    fb = faithfulness_proxy(HALLUCINATED_ANSWER, RETRIEVED_CONTEXTS)
    fr = faithfulness_proxy(REVERSED_ANSWER, RETRIEVED_CONTEXTS)
    print(f"context precision (good)      : {cp:.2f}")
    print(f"faithfulness proxy (good)     : {fg:.2f}  (>= {THRESHOLD:.2f} -> gate PASSES)")
    print(f"faithfulness proxy (regressed): {fb:.2f}  (<  {THRESHOLD:.2f} -> gate FAILS the build)")
    print(f"faithfulness proxy (reversed) : {fr:.2f}  (>= {THRESHOLD:.2f} -> passes, but the"
          " answer reverses the runbook)")
    print("ragas / trulens live judge    : validation-only (no key in CI; ragas import is")
    print("                                broken against langchain 1.x, see README)")
    assert gate(GOOD_ANSWER), "good answer should pass the gate"
    assert not gate(HALLUCINATED_ANSWER), "hallucinated answer must fail the gate"
    # Documents the limit the chapter describes: overlap is not support.
    assert gate(REVERSED_ANSWER), "the overlap proxy cannot catch a reversed instruction"


if __name__ == "__main__":
    main()
