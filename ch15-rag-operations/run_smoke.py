"""Headless end-to-end smoke test for Chapter 15. Ties labs 1-3 and the
deterministic eval gate together against the live pgvector service container and
prints 'smoke: ok' only when every assertion holds. Reads PG* env vars, so the
same script runs locally (Docker) and in CI.
"""

from __future__ import annotations

import py_compile

from incidentcopilot import bench, contextual, db, ingest
from incidentcopilot.embed import LocalEmbedder
from incidentcopilot.evaluate import hit_rate, mean_metric, precision_at_k
from incidentcopilot.rerank import FlashRankReranker
from incidentcopilot.retrieve import dense_search, hybrid_search


def rank_of_gold(hits, gold_ids: set[int]) -> int:
    for i, h in enumerate(hits, start=1):
        if h.id in gold_ids:
            return i
    return 10**6


def main() -> None:
    conn = db.connect()
    db.apply_schema(conn, "schema.sql")
    db.reset(conn)
    embedder = LocalEmbedder()
    docs = ingest.load_docs("corpus")
    docs_by_id = {d.doc_id: d for d in docs}
    chunks = [c for d in docs for c in ingest.chunk_by_heading(d)]

    # 1. ingest plain
    n_plain = ingest.ingest(conn, embedder, chunks, variant="plain")
    assert n_plain == len(chunks), "plain ingest count mismatch"

    # 2. hybrid beats dense-only on the identifier query
    q = "INC-4822 payments gateway mitigation"
    gold = bench.resolve_gold_ids(
        conn,
        [{"doc_id": "payments-incidents", "heading": "Mitigating incident INC-4822 on the payments gateway"}],
        variant="plain",
    )
    dense_rank = rank_of_gold(dense_search(conn, embedder, q, k=10), gold)
    hybrid_rank = rank_of_gold(hybrid_search(conn, embedder, q, k=10), gold)
    assert hybrid_rank < dense_rank, f"hybrid ({hybrid_rank}) must beat dense ({dense_rank})"

    # 3. reranking does not regress mean precision@5
    reranker = FlashRankReranker()
    queries = bench.load_queries("corpus/queries.json")
    p_before, p_after = [], []
    for qe in queries:
        g = bench.resolve_gold_ids(conn, qe["gold"], variant="plain")
        hybrid = hybrid_search(conn, embedder, qe["query"], k=10)
        p_before.append(precision_at_k([h.id for h in hybrid], g, 5))
        rr = reranker.rerank(conn, qe["query"], hybrid, top_k=5)
        p_after.append(precision_at_k([h.id for h in rr], g, 5))
    assert mean_metric(p_after) >= mean_metric(p_before), "rerank regressed precision"

    # 4. contextual A/B: contextual hit-rate >= plain hit-rate
    baked = contextual.load_baked_contexts("corpus/contexts.json")
    ctx_texts = []
    for c in chunks:
        ctx = baked.get(contextual.chunk_key(c)) or contextual.deterministic_context_stub(
            docs_by_id[c.doc_id], c
        )
        ctx_texts.append(contextual.prepend_context(c.content, ctx))
    ingest.ingest(conn, embedder, chunks, variant="contextual", embed_texts=ctx_texts)
    h_plain, h_ctx = [], []
    for qe in queries:
        gp = bench.resolve_gold_ids(conn, qe["gold"], variant="plain")
        gc = bench.resolve_gold_ids(conn, qe["gold"], variant="contextual")
        h_plain.append(hit_rate([h.id for h in hybrid_search(conn, embedder, qe["query"], k=3, variant="plain")], gp, 3))
        h_ctx.append(hit_rate([h.id for h in hybrid_search(conn, embedder, qe["query"], k=3, variant="contextual")], gc, 3))
    assert mean_metric(h_ctx) >= mean_metric(h_plain), "contextual regressed hit-rate"

    # 5. deterministic eval gate: good passes, hallucinated fails
    import labs.lab4_eval_gate as gate
    assert gate.gate(gate.GOOD_ANSWER)
    assert not gate.gate(gate.HALLUCINATED_ANSWER)

    # 6. validation-only modules parse (ragas is NOT imported; known broken)
    py_compile.compile("incidentcopilot/eval_ragas.py", doraise=True)
    py_compile.compile("incidentcopilot/agent.py", doraise=True)
    import trulens.core  # noqa: F401  (imports cleanly; judges are validation-only)

    conn.close()
    print("smoke: ok")


if __name__ == "__main__":
    main()
