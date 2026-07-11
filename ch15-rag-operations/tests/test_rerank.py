"""Reranking must not regress mean precision@5 on the labeled query set."""

from __future__ import annotations

from incidentcopilot import bench
from incidentcopilot.evaluate import mean_metric, precision_at_k
from incidentcopilot.rerank import FlashRankReranker
from incidentcopilot.retrieve import hybrid_search


def test_rerank_does_not_regress_precision(store):
    conn, embedder, _ = store
    reranker = FlashRankReranker()
    queries = bench.load_queries("corpus/queries.json")
    before, after = [], []
    for q in queries:
        gold = bench.resolve_gold_ids(conn, q["gold"], variant="plain")
        hybrid = hybrid_search(conn, embedder, q["query"], k=10)
        before.append(precision_at_k([h.id for h in hybrid], gold, 5))
        rr = reranker.rerank(conn, q["query"], hybrid, top_k=5)
        after.append(precision_at_k([h.id for h in rr], gold, 5))
    assert mean_metric(after) >= mean_metric(before)
